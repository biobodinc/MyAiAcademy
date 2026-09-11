"""Run model-written Python against benchmark tests in a separate, limited process.

The coding benchmark cannot be graded without executing the candidate code. The code
comes from the user's own local model and runs on the user's own machine, but it is
still untrusted output, so it runs:

* in a fresh interpreter process with ``-I`` (isolated) and ``-S`` (no site-packages),
* with an import allow-list installed before the candidate code is executed,
* in an empty scratch directory with a stripped environment,
* under a wall-clock timeout and, on POSIX, address-space, CPU-time and file-size limits.

In a PyInstaller bundle there is no ``python`` executable, so the frozen service
re-executes itself with ``--sandbox`` and dispatches to :func:`harness_main`.
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SANDBOX_FLAG = "--sandbox"
ALLOWED_IMPORTS = frozenset(
    {
        "math",
        "re",
        "string",
        "collections",
        "itertools",
        "functools",
        "json",
        "typing",
        "dataclasses",
        "heapq",
        "bisect",
        "random",
        "statistics",
        "decimal",
        "fractions",
        "operator",
        "enum",
        "copy",
        "textwrap",
        "datetime",
        "abc",
        "numbers",
    }
)
MEMORY_LIMIT_BYTES = 512 * 1024**2
OUTPUT_LIMIT_BYTES = 1024**2


@dataclass(slots=True)
class SandboxOutcome:
    results: list[bool] = field(default_factory=list)
    error: str | None = None


def run_python_tests(code: str, tests: list[str], *, timeout: float = 10.0) -> SandboxOutcome:
    """Execute ``code`` then each test expression; return one boolean per test."""
    payload = json.dumps({"code": code, "tests": tests})
    argv = (
        [sys.executable, SANDBOX_FLAG]
        if getattr(sys, "frozen", False)
        else [sys.executable, "-I", "-S", "-B", "-c", _BOOTSTRAP]
    )
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8"}
    if os.name == "nt":  # the interpreter needs these to start on Windows
        for key in ("SYSTEMROOT", "TEMP", "TMP"):
            if key in os.environ:
                env[key] = os.environ[key]
    with tempfile.TemporaryDirectory(prefix="myai-sandbox-") as scratch:
        try:
            completed = subprocess.run(
                argv,
                input=payload,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=scratch,
                env=env,
                preexec_fn=_limit_resources if os.name == "posix" else None,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return SandboxOutcome(error=f"timed out after {timeout:g}s")
        except OSError as exc:
            return SandboxOutcome(error=f"could not start the sandbox: {exc}")
    marker = completed.stdout.rfind("\n__MYAI_RESULT__")
    if marker < 0:
        tail = (completed.stderr or completed.stdout).strip().splitlines()[-1:] or ["no output"]
        return SandboxOutcome(error=f"sandbox produced no result ({tail[0][:200]})")
    try:
        data = json.loads(completed.stdout[marker + len("\n__MYAI_RESULT__") :])
    except json.JSONDecodeError:
        return SandboxOutcome(error="sandbox result was not valid JSON")
    if data.get("error"):
        return SandboxOutcome(error=str(data["error"])[:500])
    return SandboxOutcome(results=[bool(r) for r in data.get("results", [])])


def _limit_resources() -> None:  # pragma: no cover - runs in the child process
    # Only ever used as a POSIX ``preexec_fn``. The platform guard is what lets a type
    # check run on Windows, where none of these limits exist, instead of failing on a
    # branch that platform can never reach.
    if sys.platform != "win32":
        import resource

        for kind, limit in (
            (resource.RLIMIT_AS, MEMORY_LIMIT_BYTES),
            (resource.RLIMIT_CPU, 10),
            (resource.RLIMIT_FSIZE, OUTPUT_LIMIT_BYTES),
        ):
            with contextlib.suppress(ValueError, OSError):
                resource.setrlimit(kind, (limit, limit))


def harness_main() -> int:
    """Child-process entry: read the job from stdin, run it, print one result line."""
    raw = sys.stdin.read()
    try:
        job = json.loads(raw)
    except json.JSONDecodeError:
        _emit({"error": "bad job payload"})
        return 2
    _emit(_run_job(job))
    return 0


def _emit(data: dict[str, Any]) -> None:
    sys.stdout.write("\n__MYAI_RESULT__" + json.dumps(data))
    sys.stdout.flush()


def _run_job(job: dict[str, Any]) -> dict[str, Any]:
    import builtins

    real_import = builtins.__import__

    def guarded_import(name: str, *args: Any, **kwargs: Any) -> Any:
        root = name.split(".")[0]
        if root not in ALLOWED_IMPORTS:
            raise ImportError(f"import of '{name}' is not allowed in the benchmark sandbox")
        return real_import(name, *args, **kwargs)

    namespace: dict[str, Any] = {"__name__": "__candidate__", "__builtins__": builtins}
    builtins.__import__ = guarded_import
    try:
        try:
            exec(compile(str(job.get("code", "")), "<candidate>", "exec"), namespace)  # noqa: S102
        except BaseException as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}
        results: list[bool] = []
        for test in job.get("tests", []):
            try:
                results.append(bool(eval(str(test), namespace)))  # noqa: S307 - the test list is ours
            except BaseException:
                results.append(False)
        return {"results": results}
    finally:
        builtins.__import__ = real_import


_BOOTSTRAP = (
    "import sys, json\n"
    "sys.path[:] = [p for p in sys.path if p]\n"
    f"sys.path.insert(0, {str(Path(__file__).resolve().parent.parent.parent)!r})\n"
    "from myai_core.skills.sandbox import harness_main\n"
    "raise SystemExit(harness_main())\n"
)
