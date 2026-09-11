"""Deterministic graders for skill benchmarks (spec §43).

Every check is a pure function of (task, answer) so a benchmark run is reproducible
and auditable: the stored result says which check failed and why. Scores are 0..1.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from myai_core.skills.sandbox import run_python_tests

_NUMBER_RE = re.compile(r"-?\d+(?:[.,]\d+)?")
_BULLET_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+\S")
_CODE_BLOCK_RE = re.compile(r"```(?:[a-zA-Z0-9_+-]*)\n(.*?)```", re.S)


@dataclass(frozen=True, slots=True)
class CheckResult:
    check: str
    score: float
    detail: str


def normalise(text: str) -> str:
    text = text.lower().replace("\u2019", "'")
    text = re.sub(r"[^\w\s']", " ", text)
    return " ".join(text.split())


def words(text: str) -> list[str]:
    return [w for w in re.split(r"\s+", text.strip()) if w]


def numbers_in(text: str) -> list[float]:
    out: list[float] = []
    for raw in _NUMBER_RE.findall(text.replace(",", "")):
        try:
            out.append(float(raw))
        except ValueError:
            continue
    return out


def extract_code(answer: str) -> str:
    blocks = _CODE_BLOCK_RE.findall(answer)
    if blocks:
        return "\n\n".join(b.strip("\n") for b in blocks)
    return answer.strip()


def run_check(check: dict[str, Any], answer: str, prompt: str) -> CheckResult:
    kind = str(check.get("type", ""))
    handler = _CHECKS.get(kind)
    if handler is None:
        return CheckResult(kind, 0.0, f"unknown check type '{kind}'")
    try:
        return handler(check, answer, prompt)
    except Exception as exc:
        return CheckResult(kind, 0.0, f"check failed to run: {exc}")


def grade(
    checks: list[dict[str, Any]], answer: str, prompt: str
) -> tuple[float, list[CheckResult]]:
    """Mean of all checks. A task passes only when every check scores 1."""
    if not checks:
        return 0.0, [CheckResult("none", 0.0, "task has no checks")]
    results = [run_check(c, answer, prompt) for c in checks]
    return round(sum(r.score for r in results) / len(results), 4), results


# --- individual checks ------------------------------------------------------------------


def _exact(check: dict[str, Any], answer: str, _prompt: str) -> CheckResult:
    expected = check["expected"]
    options = expected if isinstance(expected, list) else [expected]
    got = normalise(answer)
    ok = any(got == normalise(str(o)) for o in options)
    return CheckResult("exact", 1.0 if ok else 0.0, f"expected one of {options!r}, got {got!r}")


def _contains_all(check: dict[str, Any], answer: str, _prompt: str) -> CheckResult:
    terms = [normalise(str(t)) for t in check["terms"]]
    got = normalise(answer)
    hits = [t for t in terms if t in got]
    score = len(hits) / len(terms) if check.get("partial") else float(len(hits) == len(terms))
    missing = [t for t in terms if t not in hits]
    return CheckResult("contains_all", score, "missing: " + ", ".join(missing) if missing else "ok")


def _contains_any(check: dict[str, Any], answer: str, _prompt: str) -> CheckResult:
    terms = [normalise(str(t)) for t in check["terms"]]
    got = normalise(answer)
    ok = any(t in got for t in terms)
    return CheckResult("contains_any", 1.0 if ok else 0.0, "ok" if ok else f"none of {terms!r}")


def _contains_none(check: dict[str, Any], answer: str, _prompt: str) -> CheckResult:
    terms = [normalise(str(t)) for t in check["terms"]]
    got = f" {normalise(answer)} "
    found = [t for t in terms if f" {t} " in got]
    return CheckResult(
        "contains_none",
        0.0 if found else 1.0,
        "found forbidden: " + ", ".join(found) if found else "ok",
    )


def _regex(check: dict[str, Any], answer: str, _prompt: str) -> CheckResult:
    flags = re.I if check.get("ignore_case", True) else 0
    if check.get("multiline"):
        flags |= re.S
    pattern = re.compile(str(check["pattern"]), flags)
    target = answer.strip()
    ok = bool(pattern.fullmatch(target) if check.get("full", False) else pattern.search(target))
    return CheckResult(
        "regex", 1.0 if ok else 0.0, "ok" if ok else f"no match for {check['pattern']!r}"
    )


def _numeric(check: dict[str, Any], answer: str, prompt: str) -> CheckResult:
    expected = float(check["expected"])
    tolerance = float(check.get("tolerance", 1e-6))
    found = numbers_in(answer)
    if not found:
        return CheckResult("numeric", 0.0, "no number in the answer")
    in_prompt = {round(n, 9) for n in numbers_in(prompt)}
    # When the expected value also appears in the question, only the final number counts.
    candidates = [found[-1]] if round(expected, 9) in in_prompt else found
    ok = any(abs(n - expected) <= tolerance for n in candidates)
    return CheckResult("numeric", 1.0 if ok else 0.0, f"expected {expected:g}, saw {candidates}")


def _word_count(check: dict[str, Any], answer: str, _prompt: str) -> CheckResult:
    n = len(words(answer))
    lo = int(check.get("min", 0))
    hi = int(check.get("max", 10**9))
    ok = lo <= n <= hi
    return CheckResult("word_count", 1.0 if ok else 0.0, f"{n} words (allowed {lo}-{hi})")


def _line_count(check: dict[str, Any], answer: str, _prompt: str) -> CheckResult:
    lines = [ln for ln in answer.strip().splitlines() if ln.strip()]
    n = len(lines)
    expected = check.get("expected")
    lo = int(check.get("min", expected if expected is not None else 0))
    hi = int(check.get("max", expected if expected is not None else 10**9))
    ok = lo <= n <= hi
    return CheckResult("line_count", 1.0 if ok else 0.0, f"{n} non-empty lines (allowed {lo}-{hi})")


def _bullets(check: dict[str, Any], answer: str, _prompt: str) -> CheckResult:
    n = sum(1 for ln in answer.splitlines() if _BULLET_RE.match(ln))
    expected = int(check["expected"])
    return CheckResult(
        "bullets", 1.0 if n == expected else 0.0, f"{n} list items (expected {expected})"
    )


def _json_object(check: dict[str, Any], answer: str, _prompt: str) -> CheckResult:
    start, end = answer.find("{"), answer.rfind("}")
    if start < 0 or end <= start:
        return CheckResult("json_object", 0.0, "no JSON object found")
    try:
        data = json.loads(answer[start : end + 1])
    except json.JSONDecodeError as exc:
        return CheckResult("json_object", 0.0, f"invalid JSON: {exc.msg}")
    if not isinstance(data, dict):
        return CheckResult("json_object", 0.0, "not a JSON object")
    expected: dict[str, Any] = check.get("expected", {})
    wrong = [k for k, v in expected.items() if normalise(str(data.get(k, ""))) != normalise(str(v))]
    return CheckResult(
        "json_object",
        0.0 if wrong else 1.0,
        "wrong or missing keys: " + ", ".join(wrong) if wrong else "ok",
    )


def _python_tests(check: dict[str, Any], answer: str, _prompt: str) -> CheckResult:
    code = extract_code(answer)
    outcome = run_python_tests(code, list(check["tests"]), timeout=float(check.get("timeout", 10)))
    if outcome.error:
        return CheckResult("python_tests", 0.0, outcome.error)
    passed = sum(outcome.results)
    total = len(outcome.results)
    score = passed / total if total else 0.0
    if check.get("all_or_nothing", True):
        score = float(passed == total)
    return CheckResult("python_tests", score, f"{passed}/{total} tests passed")


def _code_contains(check: dict[str, Any], answer: str, _prompt: str) -> CheckResult:
    code = extract_code(answer)
    pattern = re.compile(str(check["pattern"]), re.S)
    ok = bool(pattern.search(code))
    return CheckResult(
        "code_contains", 1.0 if ok else 0.0, "ok" if ok else f"code lacks {check['pattern']!r}"
    )


_CHECKS = {
    "exact": _exact,
    "contains_all": _contains_all,
    "contains_any": _contains_any,
    "contains_none": _contains_none,
    "regex": _regex,
    "numeric": _numeric,
    "word_count": _word_count,
    "line_count": _line_count,
    "bullets": _bullets,
    "json_object": _json_object,
    "python_tests": _python_tests,
    "code_contains": _code_contains,
}

CHECK_TYPES = frozenset(_CHECKS)
