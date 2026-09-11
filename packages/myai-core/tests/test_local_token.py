import os
from pathlib import Path

from myai_core.security.local_token import (
    generate_token,
    load_or_create_token,
    tokens_match,
)


def test_generate_token_is_long_and_random() -> None:
    a, b = generate_token(), generate_token()
    assert a != b
    assert len(a) >= 40


def test_load_or_create_is_stable(tmp_path: Path) -> None:
    f = tmp_path / "t"
    first = load_or_create_token(f)
    second = load_or_create_token(f)
    assert first == second
    if os.name == "posix":
        assert (f.stat().st_mode & 0o777) == 0o600


def test_existing_token_is_reused(tmp_path: Path) -> None:
    f = tmp_path / "t"
    f.write_text("  preset-token \n")
    assert load_or_create_token(f) == "preset-token"


def test_empty_file_is_replaced(tmp_path: Path) -> None:
    f = tmp_path / "t"
    f.write_text("")
    assert load_or_create_token(f)


def test_tokens_match_constant_time_semantics() -> None:
    assert tokens_match("abc", "abc")
    assert not tokens_match("abd", "abc")
    assert not tokens_match(None, "abc")
    assert not tokens_match("", "abc")
