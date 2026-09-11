"""Curated catalog of downloadable local models.

Every entry names its licence and the exact Hugging Face file. Sizes are approximate
until the download request reads ``Content-Length``; integrity is verified against the
SHA-256 the file host declares (or a pinned hash when present). Nothing here is
downloaded, or even contacted, until the user has seen the licence and accepted it.
"""

from __future__ import annotations

from pydantic import Field

from myai_core.hardware.models import HardwareTier
from myai_core.schemas import ApiModel

GiB = 1024**3
MiB = 1024**2


class ModelLicense(ApiModel):
    id: str
    name: str
    spdx: str | None = None
    url: str
    summary: str
    requires_acceptance: bool = True
    commercial_use: str = Field(description="'allowed', 'restricted' or 'see-license'.")


APACHE_2 = ModelLicense(
    id="apache-2.0",
    name="Apache License 2.0",
    spdx="Apache-2.0",
    url="https://www.apache.org/licenses/LICENSE-2.0",
    summary="Permissive. Use, modify and redistribute with attribution and licence notice.",
    commercial_use="allowed",
)
MIT = ModelLicense(
    id="mit",
    name="MIT License",
    spdx="MIT",
    url="https://opensource.org/license/mit",
    summary="Permissive. Use, modify and redistribute with the copyright notice.",
    commercial_use="allowed",
)
LLAMA_3_2 = ModelLicense(
    id="llama-3.2-community",
    name="Llama 3.2 Community License",
    spdx=None,
    url="https://www.llama.com/llama3_2/license/",
    summary=(
        "Meta's community licence. Attribution ('Built with Llama'), an acceptable-use "
        "policy, and extra terms above 700M monthly users."
    ),
    commercial_use="see-license",
)


class CatalogModel(ApiModel):
    id: str
    name: str
    family: str
    parameters_billion: float
    quantization: str
    context_length: int
    hf_repo: str
    hf_filename: str
    approx_size_bytes: int
    min_ram_bytes: int
    recommended_tiers: list[HardwareTier]
    license: ModelLicense
    description: str
    sha256: str | None = Field(
        default=None,
        description="Pinned hash when known; otherwise the host's declared hash is used.",
    )

    @property
    def download_url(self) -> str:
        return f"https://huggingface.co/{self.hf_repo}/resolve/main/{self.hf_filename}"


CATALOG: tuple[CatalogModel, ...] = (
    CatalogModel(
        id="qwen2.5-0.5b-instruct-q4km",
        name="Qwen2.5 0.5B Instruct",
        family="qwen2.5",
        parameters_billion=0.5,
        quantization="Q4_K_M",
        context_length=32768,
        hf_repo="Qwen/Qwen2.5-0.5B-Instruct-GGUF",
        hf_filename="qwen2.5-0.5b-instruct-q4_k_m.gguf",
        approx_size_bytes=490 * MiB,
        min_ram_bytes=2 * GiB,
        recommended_tiers=[HardwareTier.ENTRY],
        license=APACHE_2,
        description="Tiny and fast. Fine for trying chat on any machine; limited reasoning.",
    ),
    CatalogModel(
        id="qwen2.5-1.5b-instruct-q4km",
        name="Qwen2.5 1.5B Instruct",
        family="qwen2.5",
        parameters_billion=1.5,
        quantization="Q4_K_M",
        context_length=32768,
        hf_repo="Qwen/Qwen2.5-1.5B-Instruct-GGUF",
        hf_filename="qwen2.5-1.5b-instruct-q4_k_m.gguf",
        approx_size_bytes=1120 * MiB,
        min_ram_bytes=4 * GiB,
        recommended_tiers=[HardwareTier.ENTRY, HardwareTier.BASIC],
        license=APACHE_2,
        description="Good default for CPU-only laptops. Coherent chat, basic coding help.",
    ),
    CatalogModel(
        id="smollm2-1.7b-instruct-q4km",
        name="SmolLM2 1.7B Instruct",
        family="smollm2",
        parameters_billion=1.7,
        quantization="Q4_K_M",
        context_length=8192,
        hf_repo="HuggingFaceTB/SmolLM2-1.7B-Instruct-GGUF",
        hf_filename="smollm2-1.7b-instruct-q4_k_m.gguf",
        approx_size_bytes=1060 * MiB,
        min_ram_bytes=4 * GiB,
        recommended_tiers=[HardwareTier.ENTRY, HardwareTier.BASIC],
        license=APACHE_2,
        description="Compact model trained for instruction following and summarisation.",
    ),
    CatalogModel(
        id="llama-3.2-3b-instruct-q4km",
        name="Llama 3.2 3B Instruct",
        family="llama-3.2",
        parameters_billion=3.0,
        quantization="Q4_K_M",
        context_length=131072,
        hf_repo="bartowski/Llama-3.2-3B-Instruct-GGUF",
        hf_filename="Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        approx_size_bytes=2020 * MiB,
        min_ram_bytes=6 * GiB,
        recommended_tiers=[HardwareTier.BASIC, HardwareTier.CAPABLE],
        license=LLAMA_3_2,
        description="Strong general chat for its size. Read the community licence before use.",
    ),
    CatalogModel(
        id="phi-3.5-mini-instruct-q4km",
        name="Phi-3.5 Mini Instruct",
        family="phi-3.5",
        parameters_billion=3.8,
        quantization="Q4_K_M",
        context_length=131072,
        hf_repo="bartowski/Phi-3.5-mini-instruct-GGUF",
        hf_filename="Phi-3.5-mini-instruct-Q4_K_M.gguf",
        approx_size_bytes=2390 * MiB,
        min_ram_bytes=6 * GiB,
        recommended_tiers=[HardwareTier.BASIC, HardwareTier.CAPABLE],
        license=MIT,
        description="Reasoning-focused small model from Microsoft. Good at structured answers.",
    ),
    CatalogModel(
        id="qwen2.5-7b-instruct-q4km",
        name="Qwen2.5 7B Instruct",
        family="qwen2.5",
        parameters_billion=7.6,
        quantization="Q4_K_M",
        context_length=32768,
        hf_repo="bartowski/Qwen2.5-7B-Instruct-GGUF",
        hf_filename="Qwen2.5-7B-Instruct-Q4_K_M.gguf",
        approx_size_bytes=4680 * MiB,
        min_ram_bytes=10 * GiB,
        recommended_tiers=[HardwareTier.CAPABLE, HardwareTier.POWERFUL, HardwareTier.WORKSTATION],
        license=APACHE_2,
        description="Noticeably smarter; wants a GPU with 6 GB+ VRAM or a lot of patience on CPU.",
    ),
)

_BY_ID = {m.id: m for m in CATALOG}


def get_catalog_model(model_id: str) -> CatalogModel | None:
    return _BY_ID.get(model_id)


def all_catalog_models() -> tuple[CatalogModel, ...]:
    return CATALOG
