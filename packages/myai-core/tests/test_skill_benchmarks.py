"""Graders are deterministic, the sandbox is contained, and every bundled package is valid."""

from __future__ import annotations

import pytest

from myai_core.skills import graders, sandbox
from myai_core.skills.packages import bundled_package, bundled_skill_ids, load_package
from myai_core.skills.sandbox import run_python_tests


@pytest.mark.parametrize(
    ("check", "answer", "prompt", "expected"),
    [
        ({"type": "exact", "expected": ["ok", "ok."]}, "OK.", "", 1.0),
        ({"type": "exact", "expected": "ok"}, "okay", "", 0.0),
        ({"type": "contains_all", "terms": ["red", "blue"]}, "Red and BLUE.", "", 1.0),
        ({"type": "contains_all", "terms": ["red", "blue"], "partial": True}, "red", "", 0.5),
        ({"type": "contains_none", "terms": ["big"]}, "a bigger storm", "", 1.0),
        ({"type": "contains_none", "terms": ["big"]}, "a big storm", "", 0.0),
        ({"type": "regex", "pattern": "^(yes|no)[.!]?$", "full": True}, "Yes!", "", 1.0),
        ({"type": "numeric", "expected": 391}, "17 x 23 = 391.", "17 times 23", 1.0),
        ({"type": "numeric", "expected": 0.5}, "0.5 is larger than 0.25", "0.5 or 0.25?", 0.0),
        ({"type": "numeric", "expected": 0.5}, "The larger number is 0.5", "0.5 or 0.25?", 1.0),
        ({"type": "word_count", "max": 3}, "Paris, France.", "", 1.0),
        ({"type": "line_count", "expected": 2}, "rain falls\n\nsoft on roofs\n", "", 1.0),
        ({"type": "bullets", "expected": 3}, "- red\n- blue\n- yellow", "", 1.0),
        ({"type": "bullets", "expected": 3}, "1. towel\n2) sunscreen\n3. hat\n", "", 1.0),
        (
            {"type": "json_object", "expected": {"name": "Sam", "age": "30"}},
            'Sure: {"name": "Sam", "age": 30}',
            "",
            1.0,
        ),
        (
            {"type": "code_contains", "pattern": '"""'},
            '```python\ndef f():\n    """doc"""\n```',
            "",
            1.0,
        ),
        ({"type": "nope"}, "x", "", 0.0),
    ],
)
def test_checks(check: dict[str, object], answer: str, prompt: str, expected: float) -> None:
    result = graders.run_check(check, answer, prompt)
    assert result.score == expected, result.detail


def test_grade_is_mean_and_pass_requires_all() -> None:
    checks = [{"type": "contains_all", "terms": ["paris"]}, {"type": "word_count", "max": 1}]
    score, results = graders.grade(checks, "Paris is the capital", "")
    assert score == 0.5 and [r.score for r in results] == [1.0, 0.0]


def test_extract_code_prefers_fenced_block() -> None:
    assert graders.extract_code("Here:\n```python\nx = 1\n```\nDone") == "x = 1"
    assert graders.extract_code("x = 2") == "x = 2"


def test_sandbox_runs_tests() -> None:
    out = run_python_tests(
        "def add(a, b):\n    return a + b\n", ["add(1, 2) == 3", "add(1, 1) == 3"]
    )
    assert out.error is None and out.results == [True, False]


def test_sandbox_blocks_dangerous_imports_and_reports_errors() -> None:
    out = run_python_tests("import os\n", ["True"])
    assert out.error and "not allowed" in out.error
    out = run_python_tests("import subprocess\n", ["True"])
    assert out.error and "not allowed" in out.error
    out = run_python_tests("def f(:\n", ["True"])
    assert out.error and "SyntaxError" in out.error
    out = run_python_tests("import math\n", ["math.sqrt(16) == 4"])
    assert out.error is None and out.results == [True]


def test_sandbox_times_out() -> None:
    out = run_python_tests("while True:\n    pass\n", ["True"], timeout=2)
    assert out.error and "timed out" in out.error


@pytest.mark.skipif(
    not sandbox.MEMORY_LIMIT_ENFORCED,
    reason="only Linux enforces RLIMIT_AS against the mappings CPython uses",
)
def test_sandbox_memory_limit() -> None:
    out = run_python_tests("x = bytearray(2 * 1024**3)\n", ["True"], timeout=10)
    assert out.error and ("MemoryError" in out.error or "no result" in out.error)


def test_containment_claims_only_what_this_platform_enforces() -> None:
    """macOS accepts RLIMIT_AS and ignores it, so a memory cap must not be claimed
    there. Anything shown to a user about the sandbox comes from this list, so it is
    the thing that has to stay true on every platform."""
    measures = sandbox.containment()
    assert any("separate interpreter" in m for m in measures)
    assert any("allow-list" in m for m in measures)
    assert any("timeout" in m for m in measures)
    mentions_memory = any("address-space" in m for m in measures)
    assert mentions_memory is sandbox.MEMORY_LIMIT_ENFORCED


def test_python_tests_check_end_to_end() -> None:
    check = {"type": "python_tests", "tests": ["fact(0) == 1", "fact(5) == 120"]}
    good = "```python\ndef fact(n):\n    return 1 if n == 0 else n * fact(n - 1)\n```"
    assert graders.run_check(check, good, "").score == 1.0
    bad = "def fact(n):\n    if n == 0:\n        return 0\n    return n * fact(n - 1)"
    assert graders.run_check(check, bad, "").score == 0.0


def test_bundled_packages_are_valid_and_solvable_by_reference_answers() -> None:
    ids = bundled_skill_ids()
    assert ids == ["coding", "conversation", "research", "science", "writing"]
    for skill_id in ids:
        package = bundled_package(skill_id)
        assert package is not None and package.id == skill_id
        assert len(package.benchmark.tasks) >= 10
        assert len({t.id for t in package.benchmark.tasks}) == len(package.benchmark.tasks)
        assert package.instructions and package.size_bytes > 0


REFERENCE_ANSWERS: dict[str, dict[str, str]] = {
    "science": {
        "multiply": "391",
        "divide": "12",
        "percent": "30",
        "km-to-m": "2500",
        "hours-to-minutes": "90",
        "celsius-to-f": "212",
        "train-distance": "150 km",
        "larger-decimal": "0.5",
        "boiling-point": "100",
        "blue-sky": (
            "Sunlight scatters off air molecules; blue wavelengths scatter most "
            "(Rayleigh scattering), so blue reaches your eyes from every direction."
        ),
        "hexagon": "6",
        "prime": "Yes",
    },
    "conversation": {
        "only-ok": "OK",
        "three-colours": "- Red\n- Blue\n- Yellow",
        "capital-one-word": "Paris",
        "greet-by-name": "Hello Dana, nice to meet you!",
        "capitals-only": "TUESDAY",
        "yes-no": "Yes",
        "count-to-five": "1, 2, 3, 4, 5",
        "favourite-colour": "Green",
        "spanish-thanks": "Gracias",
        "json-person": '{"name": "Sam", "age": 30}',
        "explain-file": (
            "A computer file is a named collection of data stored on a disk so programs "
            "can read or change it later."
        ),
        "repeat-sentence": "The quick brown fox jumps over the lazy dog.",
    },
}


def test_reference_answers_score_full_marks() -> None:
    """Guards against tasks that are impossible to satisfy as written."""
    for skill_id, answers in REFERENCE_ANSWERS.items():
        package = bundled_package(skill_id)
        assert package is not None
        for task in package.benchmark.tasks:
            score, results = graders.grade(task.checks, answers[task.id], task.prompt)
            assert score == 1.0, (skill_id, task.id, [r.detail for r in results])


def test_load_package_rejects_area_mismatch(tmp_path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "skill.json").write_text(
        '{"id":"x","version":"1","name":"X","license":"MIT","summary":"s","areas":["a"],"resources":"r"}'
    )
    (tmp_path / "instructions.md").write_text("do x")
    (tmp_path / "benchmark.json").write_text(
        '{"version":"1","tasks":[{"id":"t","area":"b","prompt":"p","checks":[{"type":"exact","expected":"x"}]}]}'
    )
    with pytest.raises(ValueError, match="differ"):
        load_package(tmp_path)
