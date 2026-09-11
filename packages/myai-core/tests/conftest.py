from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from myai_core.api.app import create_app
from myai_core.config import CoreSettings
from myai_core.db.base import make_engine, make_session_factory
from myai_core.db.migrate import upgrade_to_head
from myai_core.paths import AppPaths

TEST_TOKEN = "test-token-not-secret"


@pytest.fixture
def test_token() -> str:
    return TEST_TOKEN


@pytest.fixture
def app_paths(tmp_path: Path) -> AppPaths:
    return AppPaths(tmp_path / "data").ensure()


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    engine = make_engine(tmp_path / "unit.sqlite3")
    upgrade_to_head(engine)
    factory = make_session_factory(engine)
    s = factory()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


class _NoRuntime:
    """A provider whose runtime is absent: keeps route tests independent of llama_cpp."""

    id = "test-missing"

    def availability(self) -> tuple[bool, str]:
        return False, "runtime not installed in tests"

    def load(self, model_path: Path, config: object) -> None:  # pragma: no cover
        raise RuntimeError("unavailable")

    def unload(self) -> None:
        return None

    def loaded_model_id(self) -> str | None:
        return None

    def backend_name(self) -> str | None:
        return None

    def generate(self, messages: object, options: object) -> Iterator[object]:  # pragma: no cover
        raise RuntimeError("unavailable")


@pytest.fixture
def client(app_paths: AppPaths) -> Iterator[TestClient]:
    app = create_app(CoreSettings(), app_paths, token=TEST_TOKEN, provider=_NoRuntime())
    with TestClient(app, base_url="http://127.0.0.1") as c:
        c.headers.update({"Authorization": f"Bearer {TEST_TOKEN}"})
        yield c


@pytest.fixture
def anon_client(app_paths: AppPaths) -> Iterator[TestClient]:
    app = create_app(CoreSettings(), app_paths, token=TEST_TOKEN, provider=_NoRuntime())
    with TestClient(app, base_url="http://127.0.0.1") as c:
        yield c


def build_tiny_gguf(path: Path) -> Path:
    """Write a tiny random llama-architecture GGUF (about 160 KB) that llama.cpp loads.

    It has a byte-fallback SentencePiece vocabulary, two transformer blocks and a chat
    template, so the real runtime's load, templating, tokenisation and streaming paths
    are exercised end to end. Its output is random; tests only assert that it runs.
    """
    import gguf
    import numpy as np

    n_embd, n_layer, n_ff, n_head = 32, 2, 64, 2
    writer = gguf.GGUFWriter(str(path), "llama")
    writer.add_name("tiny-test")
    writer.add_context_length(256)
    writer.add_embedding_length(n_embd)
    writer.add_block_count(n_layer)
    writer.add_feed_forward_length(n_ff)
    writer.add_head_count(n_head)
    writer.add_head_count_kv(n_head)
    writer.add_rope_dimension_count(n_embd // n_head)
    writer.add_layer_norm_rms_eps(1e-5)
    writer.add_file_type(gguf.LlamaFileType.ALL_F32)
    tokens = ["<unk>", "<s>", "</s>", *[f"<0x{i:02X}>" for i in range(256)]]
    types = [gguf.TokenType.UNKNOWN, gguf.TokenType.CONTROL, gguf.TokenType.CONTROL]
    types += [gguf.TokenType.BYTE] * 256
    words = ["▁hello", "▁world", "▁the", "▁a", "▁is", "▁you", "▁I", "▁MyAI"]
    tokens += words
    types += [gguf.TokenType.NORMAL] * len(words)
    writer.add_tokenizer_model("llama")
    writer.add_tokenizer_pre("default")
    writer.add_token_list(tokens)
    writer.add_token_scores([0.0] * len(tokens))
    writer.add_token_types(types)
    writer.add_bos_token_id(1)
    writer.add_eos_token_id(2)
    writer.add_unk_token_id(0)
    writer.add_add_bos_token(True)
    writer.add_chat_template(
        "{% for m in messages %}<|{{ m['role'] }}|>{{ m['content'] }}\n{% endfor %}<|assistant|>"
    )
    rng = np.random.default_rng(0)

    def tensor(name: str, shape: tuple[int, ...]) -> None:
        writer.add_tensor(name, (rng.standard_normal(shape) * 0.02).astype(np.float32))

    ones = np.ones(n_embd, dtype=np.float32)
    tensor("token_embd.weight", (len(tokens), n_embd))
    writer.add_tensor("output_norm.weight", ones)
    tensor("output.weight", (len(tokens), n_embd))
    for i in range(n_layer):
        writer.add_tensor(f"blk.{i}.attn_norm.weight", ones)
        for name in ("attn_q", "attn_k", "attn_v", "attn_output"):
            tensor(f"blk.{i}.{name}.weight", (n_embd, n_embd))
        writer.add_tensor(f"blk.{i}.ffn_norm.weight", ones)
        tensor(f"blk.{i}.ffn_gate.weight", (n_ff, n_embd))
        tensor(f"blk.{i}.ffn_up.weight", (n_ff, n_embd))
        tensor(f"blk.{i}.ffn_down.weight", (n_embd, n_ff))
    writer.write_header_to_file()
    writer.write_kv_data_to_file()
    writer.write_tensors_to_file()
    writer.close()
    return path


# ``--import-mode=importlib`` gives test modules no package to import helpers from, so the
# builder above is published under a stable module name for ``test_real_runtime.py``.
import sys  # noqa: E402
import types  # noqa: E402

_shim = types.ModuleType("tests_conftest_shim")
_shim.build_tiny_gguf = build_tiny_gguf  # type: ignore[attr-defined]
sys.modules.setdefault("tests_conftest_shim", _shim)
