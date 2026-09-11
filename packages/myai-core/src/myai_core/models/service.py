"""Installed models, licence acceptance, hardware fit and activation."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from ulid import ULID

from myai_core.db.models import InstalledModel, ModelDownload, ModelLicenseAcceptance
from myai_core.hardware.models import AcceleratorBackend, HardwareReport, HardwareTier
from myai_core.models.catalog import CatalogModel, all_catalog_models, get_catalog_model
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
    """A catalog model joined with local state, as the UI shows it."""

    catalog: CatalogModel
    installed: bool
    active: bool
    license_accepted: bool
    file_path: str | None
    size_bytes: int | None
    verified_sha256: str | None
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
                    catalog=model,
                    installed=installed is not None,
                    active=model.id == active,
                    license_accepted=model.id in accepted,
                    file_path=installed.file_path if installed else None,
                    size_bytes=installed.size_bytes if installed else None,
                    verified_sha256=installed.sha256 if installed else None,
                    fit=hardware_fit(model, hardware),
                    download=DownloadStatus.model_validate(download)
                    if download and download.status in {"queued", "running", "verifying", "failed"}
                    else None,
                )
            )
        return out

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
        self, model: CatalogModel, path: Path, size_bytes: int, sha256: str | None
    ) -> InstalledModel:
        row = InstalledModel(
            id=model.id,
            display_name=model.name,
            family=model.family,
            file_path=str(path),
            size_bytes=size_bytes,
            sha256=sha256,
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


def recommended_for(hardware: HardwareReport | None) -> CatalogModel:
    """The default suggestion for first-run: the largest model the tier recommends."""
    tier = hardware.tier.tier if hardware else HardwareTier.ENTRY
    candidates = [m for m in all_catalog_models() if tier in m.recommended_tiers]
    if not candidates:
        candidates = list(all_catalog_models())
    return max(candidates, key=lambda m: m.parameters_billion)
