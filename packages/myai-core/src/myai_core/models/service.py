"""Installed models, licence acceptance, hardware fit and activation."""

from __future__ import annotations

import hashlib
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from ulid import ULID

from myai_core.db.models import InstalledModel, ModelDownload, ModelLicenseAcceptance
from myai_core.hardware.models import AcceleratorBackend, HardwareReport, HardwareTier
from myai_core.models.catalog import (
    CatalogModel,
    ModelLicense,
    all_catalog_models,
    get_catalog_model,
)
from myai_core.models.download import IMPORTED, UNVERIFIED, VERIFICATION_LABELS
from myai_core.schemas import ApiModel
from myai_core.storage import StorageCategory, StorageManager

GiB = 1024**3


class HardwareFit(ApiModel):
    ok: bool
    recommended: bool
    reasons: list[str] = Field(default_factory=list)


class DownloadStatus(ApiModel):
    id: str
    model_id: str
    status: str
    bytes_done: int
    bytes_total: int | None
    error: str | None
    started_at: datetime
    finished_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class ModelEntry(ApiModel):
    """A model as the UI shows it: a catalog entry or a file the user imported, joined
    with local state."""

    id: str
    name: str
    source: Literal["catalog", "imported"]
    license: ModelLicense
    description: str
    catalog: CatalogModel | None = Field(
        default=None, description="Present for catalog models; ``None`` for imported files."
    )
    installed: bool
    active: bool
    license_accepted: bool
    file_path: str | None
    size_bytes: int | None
    file_sha256: str | None = Field(
        default=None, description="The hash computed on download. Not proof of verification."
    )
    verification: str | None = Field(
        default=None, description="What that hash was checked against, if anything."
    )
    verification_detail: str | None = Field(
        default=None, description="A sentence the UI can show verbatim."
    )
    fit: HardwareFit
    download: DownloadStatus | None


class ModelsOverview(ApiModel):
    runtime_available: bool
    runtime_detail: str
    active_model_id: str | None
    loaded_model_id: str | None
    backend: str | None
    models: list[ModelEntry]


class ModelError(ValueError):
    pass


class ProviderInfo(ApiModel):
    """One entry of the provider architecture (spec §46), reported truthfully."""

    id: str
    name: str
    kind: Literal["local", "external"]
    status: Literal["available", "unavailable", "planned"]
    detail: str


USER_SUPPLIED = ModelLicense(
    id="user-supplied",
    name="Your own licence",
    spdx=None,
    url="",
    summary=(
        "A file you imported. You confirmed that you may use it under its own licence "
        "terms; MyAI Academy did not verify them."
    ),
    requires_acceptance=False,
    commercial_use="see-license",
)

IMPORT_FOLDER = "imported"
GGUF_SUFFIX = ".gguf"


class ImportRequest(ApiModel):
    path: str = Field(min_length=1, description="Absolute path to a .gguf file.")
    name: str | None = Field(default=None, max_length=128)
    rights_confirmed: bool = Field(
        default=False,
        description="Must be true: you confirm you may use this file under its licence.",
    )


def fit_for_size(
    size_bytes: int, hardware: HardwareReport | None, parameters_billion: float | None = None
) -> HardwareFit:
    """Conservative fit for any model file: weights plus working memory must fit in RAM."""
    if hardware is None:
        return HardwareFit(ok=True, recommended=False, reasons=["Hardware not scanned yet."])
    needed = int(size_bytes * 1.25) + GiB
    ram = hardware.memory.total_bytes or 0
    reasons: list[str] = []
    ok = True
    if ram and ram < needed:
        ok = False
        reasons.append(
            f"Needs about {needed / GiB:.0f} GB RAM; this machine has {ram / GiB:.0f} GB."
        )
    gpu = hardware.primary_gpu
    accelerated = gpu is not None and gpu.backend is not AcceleratorBackend.NONE
    if (
        accelerated
        and gpu is not None
        and gpu.vram_total_bytes
        and gpu.vram_total_bytes < size_bytes
    ):
        reasons.append("Larger than the GPU's memory; some layers will run on the CPU (slower).")
    elif not accelerated and (parameters_billion or 0) >= 7:
        reasons.append("No GPU acceleration detected: a 7B model will be slow on CPU alone.")
    elif not accelerated and size_bytes >= 4 * GiB:
        reasons.append("No GPU acceleration detected: a file this large will be slow on CPU alone.")
    return HardwareFit(ok=ok, recommended=False, reasons=reasons)


def hardware_fit(model: CatalogModel, hardware: HardwareReport | None) -> HardwareFit:
    """Conservative fit check. Never claims a model will run well, only whether it fits."""
    if hardware is None:
        return HardwareFit(ok=True, recommended=False, reasons=["Hardware not scanned yet."])
    reasons: list[str] = []
    ram = hardware.memory.total_bytes or 0
    ok = True
    if ram and ram < model.min_ram_bytes:
        ok = False
        reasons.append(
            f"Needs about {model.min_ram_bytes / GiB:.0f} GB RAM; this machine has "
            f"{ram / GiB:.0f} GB."
        )
    gpu = hardware.primary_gpu
    accelerated = gpu is not None and gpu.backend is not AcceleratorBackend.NONE
    if accelerated and gpu is not None and gpu.vram_total_bytes:
        if gpu.vram_total_bytes < model.approx_size_bytes:
            reasons.append(
                "Larger than the GPU's memory; some layers will run on the CPU (slower)."
            )
    elif model.parameters_billion >= 7:
        reasons.append("No GPU acceleration detected: a 7B model will be slow on CPU alone.")
    recommended = hardware.tier.tier in model.recommended_tiers
    if not recommended and ok:
        tiers = ", ".join(t.value for t in model.recommended_tiers)
        reasons.append(f"Suggested for {tiers} machines; yours is {hardware.tier.tier.value}.")
    return HardwareFit(ok=ok, recommended=recommended and ok, reasons=reasons)


class ModelService:
    ACTIVE_MODEL_PREF = "active_model_id"

    def __init__(self, session: Session, storage: StorageManager) -> None:
        self._session = session
        self._storage = storage

    # --- queries ------------------------------------------------------------------------

    def installed(self) -> list[InstalledModel]:
        return list(
            self._session.scalars(select(InstalledModel).order_by(InstalledModel.installed_at))
        )

    def get_installed(self, model_id: str) -> InstalledModel | None:
        return self._session.get(InstalledModel, model_id)

    def active_model_id(self) -> str | None:
        from myai_core.db.models import Preference

        row = self._session.get(Preference, self.ACTIVE_MODEL_PREF)
        value = row.value if row else None
        if isinstance(value, str) and self.get_installed(value) is not None:
            return value
        return None

    def latest_download(self, model_id: str) -> ModelDownload | None:
        return self._session.scalars(
            select(ModelDownload)
            .where(ModelDownload.model_id == model_id)
            .order_by(ModelDownload.started_at.desc())
        ).first()

    def entries(self, hardware: HardwareReport | None) -> list[ModelEntry]:
        active = self.active_model_id()
        accepted = {
            row.model_id for row in self._session.scalars(select(ModelLicenseAcceptance)).all()
        }
        out: list[ModelEntry] = []
        for model in all_catalog_models():
            installed = self.get_installed(model.id)
            download = self.latest_download(model.id)
            out.append(
                ModelEntry(
                    id=model.id,
                    name=model.name,
                    source="catalog",
                    license=model.license,
                    description=model.description,
                    catalog=model,
                    installed=installed is not None,
                    active=model.id == active,
                    license_accepted=model.id in accepted,
                    file_path=installed.file_path if installed else None,
                    size_bytes=installed.size_bytes if installed else None,
                    file_sha256=installed.sha256 if installed else None,
                    verification=installed.verified_against if installed else None,
                    verification_detail=(
                        VERIFICATION_LABELS.get(installed.verified_against) if installed else None
                    ),
                    fit=hardware_fit(model, hardware),
                    download=DownloadStatus.model_validate(download)
                    if download and download.status in {"queued", "running", "verifying", "failed"}
                    else None,
                )
            )
        for row in self.installed():
            if get_catalog_model(row.id) is not None:
                continue
            out.append(
                ModelEntry(
                    id=row.id,
                    name=row.display_name,
                    source="imported",
                    license=USER_SUPPLIED,
                    description=f"Imported from {row.file_path}",
                    catalog=None,
                    installed=True,
                    active=row.id == active,
                    license_accepted=True,
                    file_path=row.file_path,
                    size_bytes=row.size_bytes,
                    file_sha256=row.sha256,
                    verification=row.verified_against,
                    verification_detail=VERIFICATION_LABELS.get(row.verified_against),
                    fit=fit_for_size(row.size_bytes, hardware),
                    download=None,
                )
            )
        return out

    # --- import ---------------------------------------------------------------------------

    def import_file(self, request: ImportRequest) -> InstalledModel:
        """Register a GGUF file the user already has (spec §46 LocalModelProvider).

        Files outside the Models folder are *copied* in (the original is untouched);
        files already inside it are registered in place. The SHA-256 is recorded so the
        file can be verified later. No licence is verified: the user asserts their rights.
        """
        if not request.rights_confirmed:
            raise ModelError(
                "Confirm that you have the right to use this model file under its licence."
            )
        if self._storage.get_config() is None:
            raise ModelError("Choose a MyAI storage location before importing models.")
        source = Path(request.path).expanduser()
        if not source.is_absolute():
            raise ModelError("Give an absolute path to the model file.")
        if not source.is_file() or source.is_symlink():
            raise ModelError(f"No such file: {source}")
        if source.suffix.lower() != GGUF_SUFFIX:
            raise ModelError("Only GGUF files (.gguf) can be imported in this version.")
        size = source.stat().st_size
        if size < 1024:
            raise ModelError("That file is too small to be a model.")
        digest = _sha256_of(source)
        for row in self.installed():
            if row.sha256 == digest:
                raise ModelError(f"That file is already installed as '{row.display_name}'.")

        models_root = self._storage.category_path(StorageCategory.MODELS).resolve()
        resolved = source.resolve()
        if resolved.is_relative_to(models_root):
            dest = resolved
        else:
            dest = models_root / IMPORT_FOLDER / source.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists() and _sha256_of(dest) != digest:
                raise ModelError(
                    f"A different file named {source.name} already exists under Models/"
                    f"{IMPORT_FOLDER}. Rename your file and try again."
                )
            if not dest.exists():
                shutil.copy2(source, dest)

        model_id = self._unique_id(f"local-{_slug(source.stem)}")
        row = InstalledModel(
            id=model_id,
            display_name=(request.name or source.stem)[:128],
            family=IMPORT_FOLDER,
            file_path=str(dest),
            size_bytes=size,
            sha256=digest,
            verified_against=IMPORTED,
            license_id=USER_SUPPLIED.id,
        )
        self._session.add(row)
        self._session.flush()
        if self.active_model_id() is None:
            self.set_active(model_id)
        return row

    def _unique_id(self, base: str) -> str:
        candidate = base
        n = 2
        while self.get_installed(candidate) is not None or get_catalog_model(candidate):
            candidate = f"{base}-{n}"
            n += 1
        return candidate

    # --- licence ------------------------------------------------------------------------

    def accept_license(self, model_id: str) -> CatalogModel:
        model = self._require_catalog(model_id)
        row = self._session.get(ModelLicenseAcceptance, model_id)
        if row is None:
            self._session.add(
                ModelLicenseAcceptance(model_id=model_id, license_id=model.license.id)
            )
        else:
            row.license_id = model.license.id
            row.accepted_at = datetime.now(tz=UTC)
        self._session.flush()
        return model

    def license_accepted(self, model_id: str) -> bool:
        return self._session.get(ModelLicenseAcceptance, model_id) is not None

    # --- install / remove / activate ----------------------------------------------------

    def target_path(self, model: CatalogModel) -> Path:
        return (
            self._storage.category_path(StorageCategory.MODELS) / model.family / model.hf_filename
        )

    def prepare_download(self, model_id: str) -> tuple[CatalogModel, Path, ModelDownload]:
        model = self._require_catalog(model_id)
        if self._storage.get_config() is None:
            raise ModelError("Choose a MyAI storage location before downloading models.")
        if not self.license_accepted(model_id):
            raise ModelError(
                f"Accept the {model.license.name} for {model.name} before downloading."
            )
        if self.get_installed(model_id) is not None:
            raise ModelError(f"{model.name} is already installed.")
        current = self.latest_download(model_id)
        if current is not None and current.status in {"queued", "running", "verifying"}:
            raise ModelError(f"{model.name} is already downloading.")
        job = ModelDownload(id=f"dl_{ULID()}", model_id=model_id, status="queued")
        self._session.add(job)
        self._session.flush()
        return model, self.target_path(model), job

    def record_installed(
        self,
        model: CatalogModel,
        path: Path,
        size_bytes: int,
        sha256: str | None,
        verified_against: str = UNVERIFIED,
    ) -> InstalledModel:
        row = InstalledModel(
            id=model.id,
            display_name=model.name,
            family=model.family,
            file_path=str(path),
            size_bytes=size_bytes,
            sha256=sha256,
            verified_against=verified_against,
            license_id=model.license.id,
        )
        self._session.merge(row)
        self._session.flush()
        if self.active_model_id() is None:
            self.set_active(model.id)
        return row

    def remove(self, model_id: str) -> None:
        row = self.get_installed(model_id)
        if row is None:
            raise ModelError("That model is not installed.")
        path = Path(row.file_path)
        if path.is_file():
            path.unlink()
        self._session.delete(row)
        if self.active_model_id() == model_id:
            self._set_pref(None)
        self._session.flush()

    def set_active(self, model_id: str | None) -> None:
        if model_id is not None and self.get_installed(model_id) is None:
            raise ModelError("Install the model before making it active.")
        self._set_pref(model_id)

    def _set_pref(self, value: str | None) -> None:
        from myai_core.db.models import Preference

        row = self._session.get(Preference, self.ACTIVE_MODEL_PREF)
        if value is None:
            if row is not None:
                self._session.delete(row)
        elif row is None:
            self._session.add(Preference(key=self.ACTIVE_MODEL_PREF, value=value))
        else:
            row.value = value
        self._session.flush()

    def _require_catalog(self, model_id: str) -> CatalogModel:
        model = get_catalog_model(model_id)
        if model is None:
            raise ModelError(f"Unknown model '{model_id}'.")
        return model


def _sha256_of(path: Path) -> str:
    with path.open("rb") as fh:
        return hashlib.file_digest(fh, "sha256").hexdigest()


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return cleaned[:48] or "model"


def list_providers(runtime_available: bool, runtime_detail: str) -> list[ProviderInfo]:
    """The provider tree from spec §46 with honest status. Only llama.cpp exists today;
    external providers are optional, unimplemented, and would keep API keys in the OS
    credential store, never in the repository or the frontend."""
    planned = (
        "Not implemented. Would be optional and off by default; API keys would live in "
        "the operating system's credential store."
    )
    return [
        ProviderInfo(
            id="llama-cpp",
            name="Local (llama.cpp)",
            kind="local",
            status="available" if runtime_available else "unavailable",
            detail=runtime_detail,
        ),
        ProviderInfo(id="openai", name="OpenAI", kind="external", status="planned", detail=planned),
        ProviderInfo(
            id="anthropic", name="Anthropic", kind="external", status="planned", detail=planned
        ),
        ProviderInfo(id="google", name="Google", kind="external", status="planned", detail=planned),
        ProviderInfo(
            id="custom",
            name="Custom endpoint",
            kind="external",
            status="planned",
            detail=planned,
        ),
    ]


def recommended_for(hardware: HardwareReport | None) -> CatalogModel:
    """The default suggestion for first-run: the largest model the tier recommends."""
    tier = hardware.tier.tier if hardware else HardwareTier.ENTRY
    candidates = [m for m in all_catalog_models() if tier in m.recommended_tiers]
    if not candidates:
        candidates = list(all_catalog_models())
    return max(candidates, key=lambda m: m.parameters_billion)
