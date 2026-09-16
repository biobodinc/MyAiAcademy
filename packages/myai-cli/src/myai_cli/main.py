"""``myai`` command-line interface (Typer)."""

from __future__ import annotations

import json
import platform
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from myai_cli import __version__
from myai_cli.client import ApiError, LocalService, ServiceNotRunningError
from myai_cli.format import human_bytes
from myai_cli.local_ai import chat, knowledge_app, memory_app, models_app

app = typer.Typer(
    name="myai",
    help="MyAI Academy: your AI, your hardware, your data, your skills.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
storage_app = typer.Typer(help="MyAI storage location and usage.", no_args_is_help=True)
profile_app = typer.Typer(help="Your AI's identity and personality.", no_args_is_help=True)
settings_app = typer.Typer(help="Experience mode, compute and appearance.", no_args_is_help=True)
jobs_app = typer.Typer(help="Background jobs: learning and benchmark runs.", no_args_is_help=True)
security_app = typer.Typer(
    help="Who may act as your AI, and taking your data out.", no_args_is_help=True
)
sync_app = typer.Typer(
    help="Keeping your own devices in step, and what never leaves this one.",
    no_args_is_help=True,
)
portable_app = typer.Typer(
    help="Carry your AI to another machine, or keep it as a backup.", no_args_is_help=True
)
projects_app = typer.Typer(
    help="Group the conversations, memories and files that belong together.",
    no_args_is_help=True,
)
app.add_typer(storage_app, name="storage")
app.add_typer(profile_app, name="profile")
app.add_typer(settings_app, name="settings")
app.add_typer(jobs_app, name="jobs")
app.add_typer(models_app, name="models")
app.add_typer(memory_app, name="memory")
app.add_typer(knowledge_app, name="knowledge")
app.add_typer(security_app, name="security")
app.add_typer(sync_app, name="sync")
app.add_typer(portable_app, name="portable")
app.add_typer(projects_app, name="projects")
app.command(name="chat")(chat)

console = Console()
err_console = Console(stderr=True)

DataDirOpt = Annotated[
    Path | None,
    typer.Option("--data-dir", envvar="MYAI_DATA_DIR", help="Override the app data directory."),
]
JsonOpt = Annotated[bool, typer.Option("--json", help="Print raw JSON instead of a table.")]


def _service(data_dir: Path | None) -> LocalService:
    try:
        return LocalService.discover(data_dir)
    except ServiceNotRunningError as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc


def _call(fn: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return fn(*args, **kwargs)
    except (ServiceNotRunningError, ApiError) as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc


def _emit_json(data: Any) -> None:
    console.print_json(json.dumps(data, default=str))


@app.callback(invoke_without_command=True)
def _root(
    version: Annotated[
        bool, typer.Option("--version", help="Show the CLI version and exit.", is_eager=True)
    ] = False,
) -> None:
    if version:
        console.print(f"myai {__version__}")
        raise typer.Exit()


@app.command()
def serve(
    data_dir: DataDirOpt = None,
    port: Annotated[int | None, typer.Option(help="Preferred loopback port.")] = None,
) -> None:
    """Start the local MyAI service in the foreground."""
    from myai_core.server import main as serve_main

    argv: list[str] = []
    if data_dir is not None:
        argv += ["--data-dir", str(data_dir)]
    if port is not None:
        argv += ["--port", str(port)]
    serve_main(argv)


@app.command()
def status(data_dir: DataDirOpt = None, as_json: JsonOpt = False) -> None:
    """Show AI, internet and training availability."""
    data = _call(_service(data_dir).get, "/status")
    if as_json:
        return _emit_json(data)
    internet = {"available": "🌐 Internet: Online", "unavailable": "🌐 Internet: Offline"}.get(
        data["internet"], "🌐 Internet: Unknown"
    )
    ai = "🧠 AI: " + data["ai"].replace("_", " ").title() + f" — {data['ai_detail']}"
    training = f"🎓 Training: {data['training'].title()} — {data['training_detail']}"
    lines = [
        internet,
        ai,
        training,
        f"🔒 Privacy mode: {data['privacy_mode']}  (cloud uploads: {data['cloud_uploads']})",
    ]
    try:
        metrics = _service(data_dir).get("/hardware/metrics")
    except (ServiceNotRunningError, ApiError):
        metrics = None
    if metrics:
        lines.append("💻 System: " + _metrics_line(metrics))
    lines.append(f"Service v{data['service_version']}")
    console.print(Panel("\n".join(lines), title="MyAI status"))


def _metrics_line(m: dict[str, Any]) -> str:
    parts = []
    if m.get("cpu_percent") is not None:
        parts.append(f"CPU {m['cpu_percent']:.0f}%")
    if m.get("memory_used_bytes") is not None:
        parts.append(
            f"RAM {human_bytes(m['memory_used_bytes'])} of "
            f"{human_bytes(m['memory']['total_bytes'])}"
        )
    gpu = m.get("gpu")
    if gpu:
        util = gpu.get("utilization_percent")
        parts.append(f"GPU {gpu['name']}" + (f" {util:.0f}%" if util is not None else ""))
    battery = m.get("battery")
    if battery and battery.get("percent") is not None:
        plugged = "plugged in" if battery.get("plugged_in") else "on battery"
        parts.append(f"Battery {battery['percent']:.0f}% ({plugged})")
    return " · ".join(parts) or "no live metrics"


@app.command()
def hardware(
    data_dir: DataDirOpt = None,
    refresh: Annotated[bool, typer.Option(help="Re-run detection.")] = False,
    benchmark: Annotated[
        bool, typer.Option(help="Run the short benchmark (memory bandwidth, inference).")
    ] = False,
    as_json: JsonOpt = False,
) -> None:
    """Show detected hardware and the estimated capability tier."""
    if benchmark:
        with console.status("Running benchmark…"):
            _call(_service(data_dir).post, "/hardware/benchmark", {})
    data = _call(_service(data_dir).get, "/hardware", refresh=refresh or None)
    if as_json:
        return _emit_json(data)
    cpu, mem, os_ = data["cpu"], data["memory"], data["os"]
    table = Table(title="Hardware", show_header=False)
    table.add_row("OS", f"{os_['system']} {os_.get('release') or ''}".strip())
    table.add_row(
        "CPU",
        f"{cpu.get('model_name') or 'unknown'} "
        f"({cpu.get('physical_cores') or '?'} cores / {cpu.get('logical_threads') or '?'} threads)",
    )
    table.add_row("RAM", human_bytes(mem.get("total_bytes")))
    if data["gpus"]:
        for gpu in data["gpus"]:
            table.add_row(
                f"GPU {gpu['index']}",
                f"{gpu['name']} — {human_bytes(gpu.get('vram_total_bytes'))} VRAM, "
                f"backend: {gpu['backend']} (via {gpu['source']})",
            )
    else:
        table.add_row("GPU", "none detected")
    tier = data["tier"]
    table.add_row("Tier", f"{tier['tier'].title()}  [dim]({tier['method']})[/dim]")
    console.print(table)
    for line in tier.get("rationale", []):
        console.print(f"  • {line}")
    for warning in data.get("warnings", []):
        console.print(f"[yellow]⚠ {warning}[/yellow]")
    bench = data.get("benchmark")
    if bench:
        console.print(
            f"Benchmark ({bench['ran_at'][:19].replace('T', ' ')}): "
            f"memory copy {bench['memory_copy_gbps']} GB/s, "
            f"RAM in use {bench['memory_pressure_percent']}%"
        )
        console.print(f"  {bench['inference_note']}")
    else:
        console.print("[dim]No benchmark yet: myai hardware --benchmark[/dim]")


@storage_app.command("show")
def storage_show(data_dir: DataDirOpt = None, as_json: JsonOpt = False) -> None:
    """Show the storage root and per-category usage."""
    data = _call(_service(data_dir).get, "/storage")
    if as_json:
        return _emit_json(data)
    if not data["configured"]:
        console.print("MyAI storage is not configured yet. Run: myai storage set-root <path>")
        return
    table = Table(title=f"MyAI storage — {data['root_path']}")
    table.add_column("Category")
    table.add_column("Used", justify="right")
    table.add_column("Files", justify="right")
    table.add_column("Location")
    for cat in data["categories"]:
        table.add_row(
            cat["category"].title() + (" 🔒" if cat["protected"] else ""),
            human_bytes(cat["bytes_used"]),
            str(cat["file_count"]),
            cat["path"],
        )
    console.print(table)
    if data.get("volume_total_bytes"):
        used = data["volume_total_bytes"] - (data.get("volume_free_bytes") or 0)
        console.print(
            f"Volume: {human_bytes(used)} used of {human_bytes(data['volume_total_bytes'])} "
            f"(MyAI: {human_bytes(data['total_bytes_used'])})"
        )


@storage_app.command("check")
def storage_check(path: str, data_dir: DataDirOpt = None) -> None:
    """Validate a folder before using it as the storage root."""
    data = _call(_service(data_dir).get, "/storage/check", path=path)
    verdict = "[green]OK[/green]" if data["ok"] else "[red]Not usable[/red]"
    console.print(f"{data['path']}: {verdict}")
    for problem in data["problems"]:
        console.print(f"  • {problem}")
    if data.get("free_bytes") is not None:
        console.print(f"  Free space: {human_bytes(data['free_bytes'])}")
    if data.get("is_removable"):
        console.print("  Removable drive detected.")


@storage_app.command("set-root")
def storage_set_root(path: str, data_dir: DataDirOpt = None) -> None:
    """Set the MyAI storage root (creates the managed folder layout)."""
    data = _call(_service(data_dir).put, "/storage/root", {"root_path": path})
    console.print(f"[green]MyAI storage configured at {data['root_path']}[/green]")


@storage_app.command("cleanup")
def storage_cleanup(
    data_dir: DataDirOpt = None,
    delete: Annotated[bool, typer.Option("--delete", help="Delete the listed files.")] = False,
    include_protected: Annotated[
        bool,
        typer.Option(
            "--include-protected",
            help="Also delete items under protected categories (cannot be undone).",
        ),
    ] = False,
    as_json: JsonOpt = False,
) -> None:
    """List (and optionally delete) leftover files: partial downloads, untracked models."""
    plan = _call(_service(data_dir).get, "/storage/cleanup")
    if as_json and not delete:
        return _emit_json(plan)
    candidates = plan["candidates"]
    if not candidates:
        console.print("Nothing to clean up.")
        return
    table = Table(title=f"Reclaimable: {human_bytes(plan['reclaimable_bytes'])}")
    table.add_column("Size", justify="right")
    table.add_column("Kind")
    table.add_column("Path")
    for c in candidates:
        table.add_row(
            human_bytes(c["size_bytes"]),
            c["kind"].replace("_", " ") + (" 🔒" if c["protected"] else ""),
            c["path"],
        )
    console.print(table)
    if not delete:
        console.print("[dim]Run again with --delete to remove them.[/dim]")
        return
    chosen = [c for c in candidates if include_protected or not c["protected"]]
    skipped = len(candidates) - len(chosen)
    if skipped:
        console.print(
            f"[yellow]Skipping {skipped} protected item(s); pass --include-protected to "
            "delete training resources. They cannot be recovered.[/yellow]"
        )
    if not chosen:
        return
    result = _call(
        _service(data_dir).post,
        "/storage/cleanup",
        {"paths": [c["path"] for c in chosen], "acknowledge_protected": include_protected},
    )
    if as_json:
        return _emit_json(result)
    console.print(
        f"[green]Deleted {len(result['deleted'])} file(s), freed "
        f"{human_bytes(result['freed_bytes'])}[/green]"
    )
    for line in result["refused"]:
        console.print(f"[yellow]⚠ {line}[/yellow]")


@profile_app.command("show")
def profile_show(data_dir: DataDirOpt = None, as_json: JsonOpt = False) -> None:
    """Show your AI's profile."""
    data = _call(_service(data_dir).get, "/profile")
    if as_json:
        return _emit_json(data)
    if data is None:
        console.print("No AI yet. Create one: myai profile create --name Nova")
        return
    console.print(
        Panel(
            "\n".join(
                [
                    f"Name: {data['name']}",
                    f"Personality: {data['personality'] or '—'}",
                    f"Style: {data['communication_style'] or '—'}",
                    f"Owner: {data['owner_name'] or '—'}",
                    f"Interests: {', '.join(data['interests']) or '—'}",
                    f"Goals: {', '.join(data['goals']) or '—'}",
                    f"[dim]AI ID: {data['ai_id']}  (v{data['version']})[/dim]",
                ]
            ),
            title="MyAI",
        )
    )


@profile_app.command("create")
def profile_create(
    name: Annotated[str, typer.Option(prompt="Name your AI")],
    owner: Annotated[str, typer.Option(help="Your name (optional).")] = "",
    personality: Annotated[str, typer.Option(help="e.g. 'Helpful, curious, concise'")] = "",
    interest: Annotated[list[str] | None, typer.Option(help="Repeatable.")] = None,
    data_dir: DataDirOpt = None,
) -> None:
    """Create your AI's identity."""
    body = {
        "name": name,
        "owner_name": owner,
        "personality": personality,
        "interests": interest or [],
    }
    data = _call(_service(data_dir).post, "/profile", body)
    console.print(f"[green]Created {data['name']}[/green]  [dim]{data['ai_id']}[/dim]")


@profile_app.command("set")
def profile_set(
    name: Annotated[str | None, typer.Option()] = None,
    owner: Annotated[str | None, typer.Option()] = None,
    personality: Annotated[str | None, typer.Option()] = None,
    style: Annotated[str | None, typer.Option(help="Communication style.")] = None,
    data_dir: DataDirOpt = None,
) -> None:
    """Update profile fields."""
    body = {
        k: v
        for k, v in {
            "name": name,
            "owner_name": owner,
            "personality": personality,
            "communication_style": style,
        }.items()
        if v is not None
    }
    if not body:
        err_console.print("Nothing to change.")
        raise typer.Exit(code=1)
    data = _call(_service(data_dir).patch, "/profile", body)
    console.print(f"[green]Updated {data['name']} (v{data['version']})[/green]")


@app.command()
def skills(data_dir: DataDirOpt = None, as_json: JsonOpt = False) -> None:
    """List skills and levels."""
    data = _call(_service(data_dir).get, "/skills")
    if as_json:
        return _emit_json(data)
    table = Table(title=f"Skills — overall level {data['overall_level']}")
    table.add_column("Skill")
    table.add_column("Level", justify="right")
    table.add_column("Band")
    table.add_column("Status")
    for s in data["skills"]:
        if s["learned"]:
            state = f"learned (package {s['package_version']})"
        elif not s["learnable"]:
            state = f"no benchmark yet (Phase {s['planned_phase']})"
        elif s["locked"]:
            state = "locked: " + s["locked_reason"]
        else:
            state = f"ready: myai learn {s['id']}"
        table.add_row(f"{s['icon']} {s['name']}", str(s["level"]), s["band"], state)
    console.print(table)
    earned = [d for d in data.get("degrees", []) if d["earned"]]
    if earned:
        console.print("🎓 Degrees: " + ", ".join(f"{d['name']} L{d['level']}" for d in earned))
    badges = [a for a in data.get("achievements", []) if a["earned"]]
    if badges:
        console.print("🏅 Achievements: " + ", ".join(f"{a['icon']} {a['name']}" for a in badges))


@app.command()
def learn(
    skill: str,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Start without confirming.")] = False,
    wait: Annotated[bool, typer.Option(help="Wait for the benchmark to finish.")] = True,
    data_dir: DataDirOpt = None,
) -> None:
    """Learn a skill: install its package and run its benchmark with your local model."""
    svc = _service(data_dir)
    preview = _call(svc.get, f"/skills/{skill}/learn-preview")
    if preview["already_learned"]:
        console.print(f"{preview['icon']} {preview['name']} is already learned.")
        console.print(f"Re-run its benchmark with: myai evaluate {skill}")
        return
    if preview["blockers"]:
        err_console.print(
            f"[yellow]{preview['icon']} {preview['name']} cannot be learned yet:[/yellow]"
        )
        for b in preview["blockers"]:
            err_console.print(f"  • {b}")
        raise typer.Exit(code=1)
    pkg = preview["package"]
    if preview["estimated_minutes_min"] is not None:
        estimate = (
            f"{preview['estimated_minutes_min']:g}-{preview['estimated_minutes_max']:g} min "
            f"({preview['estimate_note']})"
        )
    else:
        estimate = f"unknown ({preview['estimate_note']})"
    console.print(
        Panel(
            "\n".join(
                [
                    preview["what_happens"],
                    "",
                    f"Resources: {human_bytes(pkg['size_bytes'])} ({pkg['resources']})",
                    f"Benchmark: {pkg['task_count']} tasks across {', '.join(pkg['areas'])}",
                    f"Model: {preview['model_id']}",
                    f"Recommended compute: {preview['recommended_compute']}",
                    f"Estimated learning preparation: {estimate}",
                ]
            ),
            title=f"{preview['icon']} New skill: {preview['name']}",
        )
    )
    if not yes and not typer.confirm("Start learning?", default=True):
        raise typer.Exit(code=1)
    job = _call(svc.post, f"/skills/{skill}/learn", {})
    console.print(f"Started job {job['id']}. The skill counts as learned only when it finishes.")
    if wait:
        _follow_job(svc, job["id"])


@app.command()
def evaluate(
    skill: str,
    wait: Annotated[bool, typer.Option(help="Wait for the benchmark to finish.")] = True,
    data_dir: DataDirOpt = None,
) -> None:
    """Re-run a learned skill's benchmark (levels only change this way)."""
    svc = _service(data_dir)
    job = _call(svc.post, f"/skills/{skill}/evaluate", {})
    console.print(f"Started job {job['id']}.")
    if wait:
        _follow_job(svc, job["id"])


@app.command()
def train(
    skill: str,
    duration: Annotated[
        str | None, typer.Option(help="How long to practise, e.g. 30m or 2h. Default 15m.")
    ] = None,
    level: Annotated[int | None, typer.Option(min=1, max=100, help="Stop at this level.")] = None,
    focus: Annotated[str | None, typer.Option(help="Practise one area (see myai skills).")] = None,
    all_areas: Annotated[bool, typer.Option("--all", help="Practise every area.")] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Start without confirming.")] = False,
    wait: Annotated[bool, typer.Option(help="Wait for training to finish.")] = True,
    data_dir: DataDirOpt = None,
) -> None:
    """Practise a learned skill: search for better instructions, measured by its benchmark.

    Your model's weights are never changed. Training tries short rules and worked examples,
    keeps only what scores better on practice tasks, and then re-runs the benchmark to
    decide whether the result is kept at all.
    """
    svc = _service(data_dir)
    request: dict[str, Any] = {"all_areas": all_areas}
    if duration is not None:
        request["duration_seconds"] = _duration_seconds(duration)
    if level is not None:
        request["target_level"] = level
    if focus is not None:
        request["specialization"] = focus
    preview = _call(svc.post, f"/skills/{skill}/train-preview", request)
    if preview["blockers"]:
        err_console.print(
            f"[yellow]{preview['icon']} {preview['name']} cannot be trained yet:[/yellow]"
        )
        for b in preview["blockers"]:
            err_console.print(f"  • {b}")
        raise typer.Exit(code=1)
    if preview["estimated_rounds_min"] is not None:
        rounds = (
            f"{preview['estimated_rounds_min']}-{preview['estimated_rounds_max']} rounds "
            f"({preview['estimate_note']})"
        )
    else:
        rounds = f"unknown ({preview['estimate_note']})"
    areas = ", ".join(
        f"{k.replace('_', ' ')} {round(v * 100)}%" for k, v in preview["last_area_scores"].items()
    )
    lines = [
        preview["what_happens"],
        "",
        f"Current level: {preview['current_level']}",
        f"Target level: {preview['target_level'] or preview['recommended_target']}",
        f"Last benchmark by area: {areas or 'none yet'}",
        preview["focus_note"],
        f"Time budget: {preview['budget_minutes']:g} minutes. {preview['budget_note']}",
        f"Practice: {preview['search_tasks']} tasks to search with, "
        f"{preview['check_tasks']} to confirm with. The benchmark stays separate.",
        f"Estimated: {rounds}",
        f"Model: {preview['model_id']}",
    ]
    if preview["resume_rounds"]:
        lines.append(f"Continuing from an earlier run of {preview['resume_rounds']} rounds.")
    console.print(Panel("\n".join(lines), title=f"{preview['icon']} Training {preview['name']}"))
    if not yes and not typer.confirm("Start training?", default=True):
        raise typer.Exit(code=1)
    job = _call(svc.post, f"/skills/{skill}/train", request)
    console.print(f"Started job {job['id']}. The benchmark decides whether the result is kept.")
    if wait:
        _follow_job(svc, job["id"])


@app.command()
def training(
    skill: str,
    revert: Annotated[
        bool, typer.Option("--revert", help="Put back the instructions the package shipped with.")
    ] = False,
    data_dir: DataDirOpt = None,
    as_json: JsonOpt = False,
) -> None:
    """Training runs for a skill, or --revert to undo what training changed."""
    svc = _service(data_dir)
    if revert:
        item = _call(svc.post, f"/skills/{skill}/training/revert", {})
        console.print(
            f"{item['name']} is back to its package instructions. Its level is unchanged "
            f"(level {item['level']}): re-run the benchmark with 'myai evaluate {skill}' "
            "to measure the original."
        )
        return
    data = _call(svc.get, f"/skills/{skill}/training")
    if as_json:
        return _emit_json(data)
    if not data:
        console.print(f"No training runs for {skill} yet. Start one with: myai train {skill}")
        return
    table = Table(title=f"Training runs: {skill}")
    table.add_column("When")
    table.add_column("Rounds", justify="right")
    table.add_column("Benchmark")
    table.add_column("Level", justify="right")
    table.add_column("Outcome")
    for run in data:
        before, after = run["benchmark_before"], run["benchmark_after"]
        bench = (
            f"{round(before * 100)}% → {round(after * 100)}%"
            if before is not None and after is not None
            else (f"{round(before * 100)}%" if before is not None else "—")
        )
        level = (
            f"{run['level_before']} → {run['level_after']}"
            if run["level_before"] is not None
            else "—"
        )
        table.add_row(
            run["started_at"][:16].replace("T", " "),
            str(run["rounds_completed"]),
            bench,
            level,
            "kept" if run["applied"] else run["status"].replace("_", " "),
        )
    console.print(table)
    console.print(data[0]["summary"])


def _duration_seconds(text: str) -> int:
    """Accept '90', '90m', '1.5h' the way the /train command does."""
    raw = text.strip().lower()
    try:
        if raw.endswith("h"):
            return int(float(raw[:-1]) * 3600)
        if raw.endswith("m"):
            return int(float(raw[:-1]) * 60)
        return int(float(raw) * 60)
    except ValueError:
        err_console.print(f"[red]Could not read a duration from '{text}'. Try 30m or 2h.[/red]")
        raise typer.Exit(code=2) from None


@app.command()
def history(
    data_dir: DataDirOpt = None,
    limit: Annotated[int, typer.Option(min=1, max=500)] = 30,
    as_json: JsonOpt = False,
) -> None:
    """Benchmark history: every level change, when, with which model."""
    data = _call(_service(data_dir).get, "/skills/history", limit=limit)
    if as_json:
        return _emit_json(data)
    if not data:
        console.print("No benchmark runs yet. Levels only ever change through them.")
        return
    table = Table(title="Benchmark history")
    table.add_column("When")
    table.add_column("Skill")
    table.add_column("Level", justify="right")
    table.add_column("Score", justify="right")
    table.add_column("Model")
    for e in data:
        table.add_row(
            e["evaluated_at"][:16].replace("T", " "),
            e["skill_id"],
            f"{e['level_before']} → {e['level_after']}",
            f"{round(e['score'] * 100)}%",
            e["model_id"],
        )
    console.print(table)


def _follow_job(svc: LocalService, job_id: str) -> None:
    import time

    last = -1
    while True:
        job = _call(svc.get, f"/jobs/{job_id}")
        total = job["progress_total"] or 0
        pct = int(job["progress_done"] * 100 / total) if total else 0
        if pct != last:
            console.print(f"  {job['status']}: {job['progress_done']}/{total} tasks ({pct}%)")
            last = pct
        if job["status"] in {"completed", "failed", "cancelled"}:
            break
        time.sleep(1.0)
    if job["status"] == "completed":
        r = job["result"]
        if job["kind"] == "train":
            _print_training_result(job["skill_id"], r)
        else:
            console.print(
                f"[green]Done: {job['skill_id']} level {r['level_before']} → {r['level_after']} "
                f"({round(r['score'] * 100)}% in {r['duration_seconds']}s)[/green]"
            )
            for area, score in r.get("area_scores", {}).items():
                console.print(f"  {area}: {round(score * 100)}%")
    elif job["status"] == "failed":
        err_console.print(f"[red]Failed: {job['error']}[/red]")
        raise typer.Exit(code=1)
    else:
        verb = "trained" if job["kind"] == "train" else "learned"
        console.print(f"[yellow]Cancelled. Nothing was {verb}.[/yellow]")


def _print_training_result(skill_id: str, r: dict[str, Any]) -> None:
    """Training's result is a decision, not a score: say what was kept and why."""
    colour = "green" if r.get("applied") else "yellow"
    console.print(f"[{colour}]{skill_id}: {r.get('summary', 'Training finished.')}[/{colour}]")
    console.print(
        f"  Rounds: {r.get('rounds', 0)} tried, {r.get('accepted_rounds', 0)} kept "
        f"({r.get('stopped_because', '')})"
    )
    before, after = r.get("practice_before"), r.get("practice_after")
    if before is not None and after is not None:
        console.print(
            f"  Practice (confirmation split): {round(before * 100)}% → {round(after * 100)}%"
        )
    console.print(f"  Level: {r.get('level_before')} → {r.get('level_after')}")


@jobs_app.command("list")
def jobs_list(data_dir: DataDirOpt = None, as_json: JsonOpt = False) -> None:
    """Recent jobs."""
    data = _call(_service(data_dir).get, "/jobs")
    if as_json:
        return _emit_json(data)
    table = Table(title="Jobs")
    table.add_column("Id")
    table.add_column("Kind")
    table.add_column("Skill")
    table.add_column("Status")
    table.add_column("Progress")
    for j in data:
        total = j["progress_total"] or 0
        table.add_row(
            j["id"], j["kind"], j["skill_id"], j["status"], f"{j['progress_done']}/{total}"
        )
    console.print(table)


def _job_action(action: str, data_dir: Path | None) -> None:
    svc = _service(data_dir)
    current = _call(svc.get, "/jobs/current")
    if current is None:
        err_console.print("No job is running.")
        raise typer.Exit(code=1)
    job = _call(svc.post, f"/jobs/{current['id']}/{action}", {})
    console.print(f"{job['kind']} {job['skill_id']}: {job['status']}")


@jobs_app.command("pause")
def jobs_pause(data_dir: DataDirOpt = None) -> None:
    """Pause the running job."""
    _job_action("pause", data_dir)


@jobs_app.command("resume")
def jobs_resume(data_dir: DataDirOpt = None) -> None:
    """Resume a paused job."""
    _job_action("resume", data_dir)


@jobs_app.command("stop")
def jobs_stop(data_dir: DataDirOpt = None) -> None:
    """Stop the running job. A stopped learning job leaves the skill unlearned."""
    _job_action("cancel", data_dir)


@app.command()
def ask(question: str, data_dir: DataDirOpt = None, as_json: JsonOpt = False) -> None:
    """Ask the built-in guide about MyAI Academy (not your AI model)."""
    data = _call(_service(data_dir).post, "/guide/ask", {"question": question})
    if as_json:
        return _emit_json(data)
    console.print(Panel(data["answer"], title=data["title"], subtitle=data["source"]))
    if data.get("related"):
        console.print("Related: " + "  ·  ".join(r["question"] for r in data["related"]))


@settings_app.command("show")
def settings_show(data_dir: DataDirOpt = None, as_json: JsonOpt = False) -> None:
    """Show current settings."""
    data = _call(_service(data_dir).get, "/preferences")
    if as_json:
        return _emit_json(data)
    table = Table(title="Settings", show_header=False)
    table.add_row("Mode", data["experience_mode"])
    table.add_row("Compute", data["compute_preset"])
    table.add_row("Theme", data["theme"])
    table.add_row("Contributor mode", "on" if data["contributor_mode"] else "off")
    for key in (
        "cpu_utilization_percent",
        "gpu_utilization_percent",
        "ram_limit_gib",
        "temperature_limit_c",
        "time_limit_minutes",
    ):
        value = data.get(key)
        table.add_row(key.replace("_", " "), "—" if value is None else str(value))
    console.print(table)


@settings_app.command("set")
def settings_set(
    mode: Annotated[str | None, typer.Option(help="beginner | advanced")] = None,
    compute: Annotated[str | None, typer.Option(help="low | balanced | high | maximum")] = None,
    theme: Annotated[str | None, typer.Option(help="system | light | dark")] = None,
    cpu: Annotated[int | None, typer.Option(help="CPU utilisation % (10-100), 0 clears")] = None,
    ram_limit: Annotated[float | None, typer.Option(help="RAM limit in GB, 0 clears")] = None,
    data_dir: DataDirOpt = None,
) -> None:
    """Change settings. Advanced limits are enforced as described by `myai ask compute`."""
    body: dict[str, Any] = {}
    if mode is not None:
        body["experience_mode"] = mode
    if compute is not None:
        body["compute_preset"] = compute
    if theme is not None:
        body["theme"] = theme
    if cpu is not None:
        body["cpu_utilization_percent"] = cpu or None
    if ram_limit is not None:
        body["ram_limit_gib"] = ram_limit or None
    if not body:
        err_console.print("Nothing to change.")
        raise typer.Exit(code=1)
    data = _call(_service(data_dir).patch, "/preferences", body)
    console.print(
        f"[green]Mode {data['experience_mode']}, compute {data['compute_preset']}, "
        f"theme {data['theme']}[/green]"
    )


@app.command()
def run(text: str, data_dir: DataDirOpt = None, as_json: JsonOpt = False) -> None:
    """Run a slash command, e.g. myai run "/train video 4h"."""
    data = _call(_service(data_dir).post, "/commands", {"text": text})
    if as_json:
        return _emit_json(data)
    colour = {"ok": "green", "unavailable": "yellow", "error": "red"}[data["outcome"]]
    if data.get("command"):
        c = data["command"]
        mapped = " (from natural language)" if c["natural_language"] else ""
        console.print(
            f"[dim]→ /{c['name']}{' ' + ' '.join(c['args']) if c['args'] else ''}{mapped}[/dim]"
        )
    console.print(Panel(data["message"], title=f"[{colour}]{data['title']}[/{colour}]"))
    if data.get("suggestions"):
        console.print("Try: " + "  ".join(data["suggestions"]))


@app.command()
def audit(
    data_dir: DataDirOpt = None,
    limit: Annotated[int, typer.Option(min=1, max=1000)] = 50,
    as_json: JsonOpt = False,
) -> None:
    """Show local security activity."""
    data = _call(_service(data_dir).get, "/audit", limit=limit)
    if as_json:
        return _emit_json(data)
    table = Table(title="Security activity")
    table.add_column("When")
    table.add_column("Category")
    table.add_column("Event")
    for e in data:
        table.add_row(e["occurred_at"][:19].replace("T", " "), e["category"], e["summary"])
    console.print(table)


@security_app.command("show")
def security_show(data_dir: DataDirOpt = None, as_json: JsonOpt = False) -> None:
    """What protects this installation right now."""
    data = _call(_service(data_dir).get, "/security")
    if as_json:
        return _emit_json(data)
    storage = data["secret_storage"]
    if storage["checked"]:
        secrets_line = "owner only" if storage["owner_only"] is not False else "READABLE BY OTHERS"
    else:
        secrets_line = "not checkable on this platform"
    lines = [
        f"You are: {data['caller_name']}"
        + (" (this installation)" if data["caller_is_owner"] else ""),
        "Listening on: 127.0.0.1 only"
        if data["bound_to_loopback"]
        else "Listening beyond loopback",
        f"Paired clients: {data['active_clients']} active, {data['revoked_clients']} revoked",
        f"Secret storage: {secrets_line}",
        f"Account: {'linked' if data['account']['linked'] else 'none'}",
        "",
        data["account"]["detail"],
    ]
    for problem in storage["problems"]:
        lines.append(f"[yellow]{problem}[/yellow]")
    console.print(Panel("\n".join(lines), title="Security"))
    for note in data["notes"]:
        console.print(f"  • {note}")


@security_app.command("clients")
def security_clients(data_dir: DataDirOpt = None, as_json: JsonOpt = False) -> None:
    """Clients that hold a credential for this AI."""
    data = _call(_service(data_dir).get, "/security/devices")
    if as_json:
        return _emit_json(data)
    if not data:
        console.print("No paired clients. Only this installation's own token can be used.")
        return
    table = Table(title="Paired clients")
    table.add_column("Id")
    table.add_column("Name")
    table.add_column("Kind")
    table.add_column("Last seen")
    table.add_column("State")
    table.add_column("May")
    for d in data:
        allowed = d.get("capabilities") or []
        table.add_row(
            d["id"],
            d["name"],
            d["kind"],
            (d["last_seen_at"] or "never")[:19].replace("T", " "),
            "revoked" if d["revoked_at"] else "active",
            ", ".join(allowed) if allowed else "nothing",
        )
    console.print(table)
    console.print("`myai security grant <id> --can <capability>` changes what a client may do.")


@security_app.command("pairing-code")
def security_pairing_code(
    label: Annotated[str, typer.Option(help="What you are pairing, for the log.")] = "",
    capability: Annotated[
        list[str] | None,
        typer.Option("--can", help="A capability to allow. Repeat for several."),
    ] = None,
    preset: Annotated[
        str, typer.Option(help="'default', 'mobile' or 'full' instead of listing them.")
    ] = "",
    data_dir: DataDirOpt = None,
) -> None:
    """Create a single-use code so a client can get its own credential.

    What the client will be allowed to do is decided here, by you. Without --can or
    --preset it gets the default grant, which includes nothing you have written.
    """
    body: dict[str, Any] = {"label": label}
    if preset:
        body["preset"] = preset
    if capability:
        body["capabilities"] = list(capability)
    data = _call(_service(data_dir).post, "/security/pairing-codes", body)
    console.print(Panel(f"[bold]{data['code']}[/bold]", title="Pairing code"))
    allowed = data.get("capabilities") or []
    console.print(
        "The client redeeming this will be allowed to: "
        + (", ".join(allowed) if allowed else "nothing at all.")
    )
    console.print(f"Expires in {data['expires_in_seconds'] // 60} minutes. {data['note']}")


@security_app.command("pair")
def security_pair(
    code: str,
    name: Annotated[str, typer.Option(help="How this client should appear in your log.")] = "",
    data_dir: DataDirOpt = None,
) -> None:
    """Redeem a pairing code and print the credential. It is shown once."""
    body = {"code": code, "name": name or f"CLI on {platform.node()}", "kind": "cli"}
    data = _call(_service(data_dir).post, "/security/pair", body)
    console.print(Panel(data["token"], title=f"Credential for {data['device']['name']}"))
    console.print(data["note"])


@security_app.command("revoke")
def security_revoke(
    device_id: str,
    reason: Annotated[str, typer.Option(help="Why, for the log.")] = "",
    data_dir: DataDirOpt = None,
) -> None:
    """Stop a client from acting as your AI, from its next request."""
    data = _call(
        _service(data_dir).post, f"/security/devices/{device_id}/revoke", {"reason": reason}
    )
    console.print(f"{data['name']} can no longer act as your AI. {data['revoked_reason']}")


@security_app.command("network")
def security_network(
    on: Annotated[
        bool | None, typer.Option("--on/--off", help="Turn network access on or off.")
    ] = None,
    port: Annotated[int | None, typer.Option(min=1024, max=65535)] = None,
    data_dir: DataDirOpt = None,
) -> None:
    """Whether paired devices on this network may reach your AI. Off unless you turn it on."""
    svc = _service(data_dir)
    if on is None:
        data = _call(svc.get, "/security")["network"]
    else:
        body: dict[str, Any] = {"enabled": on}
        if port is not None:
            body["port"] = port
        data = _call(svc.post, "/security/network", body)
    lines = [data["detail"]]
    if data["enabled"]:
        where = ", ".join(f"{a}:{data['port']}" for a in data["addresses"])
        lines += [
            f"Reachable at: {where}",
            f"Certificate: {data['certificate_fingerprint_groups']}",
            f"Key pin: {data['public_key_pin']}",
            "A device pins those when it pairs and then accepts only this computer. Compare "
            "the certificate line by eye; the key pin is the form pinning libraries take.",
        ]
    console.print(Panel("\n".join(lines), title="Devices on your network"))


@security_app.command("invite")
def security_invite(
    label: Annotated[str, typer.Option(help="What you are pairing, for the log.")] = "",
    data_dir: DataDirOpt = None,
    as_json: JsonOpt = False,
) -> None:
    """A pairing code plus the certificate a device should pin. Show it on the device."""
    data = _call(_service(data_dir).post, "/security/pairing-invite", {"label": label})
    if as_json:
        return _emit_json(data)
    console.print(
        Panel(
            "\n".join(
                [
                    f"Code: [bold]{data['code']}[/bold]",
                    f"Host: {data['host_name']} at "
                    + ", ".join(f"{a}:{data['port']}" for a in data["addresses"]),
                    f"Certificate: {data['certificate_fingerprint_groups']}",
                    "",
                    data["note"],
                ]
            ),
            title="Pair a device",
        )
    )
    console.print("QR payload (encode this if you want to scan it):")
    console.print(data["payload"])


@security_app.command("export")
def security_export(
    destination: Annotated[str | None, typer.Option(help="Where to write the archive.")] = None,
    include_files: Annotated[
        bool, typer.Option("--include-files", help="Copy your storage files too (large).")
    ] = False,
    data_dir: DataDirOpt = None,
) -> None:
    """Write an archive of everything this installation holds about you."""
    body: dict[str, Any] = {"include_model_files": include_files}
    if destination:
        body["destination"] = destination
    data = _call(_service(data_dir).post, "/privacy/export", body)
    console.print(f"Exported to {data['path']} ({human_bytes(data['size_bytes'])}).")
    manifest = data["manifest"]
    console.print(f"  Rows: {sum(manifest['row_counts'].values())} across your tables")
    console.print(
        f"  Files listed: {manifest['file_count']} ({human_bytes(manifest['file_bytes'])})"
    )
    for line in manifest["excludes"]:
        console.print(f"  Not included: {line}")


@security_app.command("erase")
def security_erase(
    remove_files: Annotated[
        bool, typer.Option("--remove-files", help="Also delete files under your storage root.")
    ] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip the confirmation prompt.")] = False,
    data_dir: DataDirOpt = None,
) -> None:
    """Delete everything this installation holds about you. This cannot be undone."""
    svc = _service(data_dir)
    plan = _call(svc.get, "/privacy/erase-preview")
    rows = sum(plan["row_counts"].values())
    console.print(
        Panel(
            "\n".join(
                [
                    f"{rows} rows of your data would be deleted.",
                    f"Storage root: {plan['storage_root'] or 'not configured'} "
                    f"({plan['storage_file_count']} files, {human_bytes(plan['storage_bytes'])})",
                    "Files will also be deleted." if remove_files else "Files will be left alone.",
                    *plan["warnings"],
                ]
            ),
            title="[red]Erase everything[/red]",
        )
    )
    if not yes:
        typed = typer.prompt(f"Type '{plan['confirmation_phrase']}' to confirm", default="")
        if typed != plan["confirmation_phrase"]:
            console.print("Nothing was deleted.")
            raise typer.Exit(code=1)
    data = _call(
        svc.post,
        "/privacy/erase",
        {"confirm": plan["confirmation_phrase"], "remove_files": remove_files},
    )
    console.print(
        f"Deleted {sum(data['rows_deleted'].values())} rows and {data['files_deleted']} files."
    )
    for note in data["notes"]:
        console.print(f"  • {note}")


@sync_app.command("status")
def sync_status(data_dir: DataDirOpt = None, as_json: JsonOpt = False) -> None:
    """What syncing is, which of your devices are in it, and what never leaves."""
    data = _call(_service(data_dir).get, "/sync")
    if as_json:
        return _emit_json(data)

    lines = [data["detail"], "", f"This installation: {data['install_id']}"]
    if data["peers"]:
        lines.append("")
        lines.append("Your other devices:")
        for peer in data["peers"]:
            seen = peer["last_synced_at"] or "never"
            lines.append(f"  • {peer['name']} — last synced {seen}")
    else:
        lines += ["", "No other device has synced with this one yet."]
    if data["unresolved_conflicts"]:
        lines += [
            "",
            f"{data['unresolved_conflicts']} change(s) were replaced by another device. "
            "`myai sync conflicts` shows what was overwritten; nothing was thrown away.",
        ]
    lines += ["", "Travels between your devices: " + ", ".join(k["name"] for k in data["syncs"])]
    lines.append(f"Never leaves this machine: {len(data['stays_local'])} kinds of record.")
    console.print(Panel("\n".join(lines), title="Sync"))


@sync_app.command("stays-local")
def sync_stays_local(data_dir: DataDirOpt = None, as_json: JsonOpt = False) -> None:
    """Everything that never leaves this machine, and why not."""
    data = _call(_service(data_dir).get, "/sync")["stays_local"]
    if as_json:
        return _emit_json(data)
    table = Table("Record", "Why it stays here")
    for name, reason in sorted(data.items()):
        table.add_row(name, reason)
    console.print(table)


@sync_app.command("conflicts")
def sync_conflicts(
    all_of_them: Annotated[
        bool, typer.Option("--all", help="Include ones you have already looked at.")
    ] = False,
    data_dir: DataDirOpt = None,
    as_json: JsonOpt = False,
) -> None:
    """Changes that two devices made at once. The version that lost is kept, not deleted."""
    data = _call(_service(data_dir).get, "/sync/conflicts", include_resolved=all_of_them)
    if as_json:
        return _emit_json(data)
    if not data:
        console.print("No conflicts. Your devices agree.")
        return
    table = Table("id", "What", "Kept", "What was replaced")
    for row in data:
        replaced = row["losing_payload"].get("title") or row["losing_payload"].get("content") or ""
        table.add_row(str(row["id"]), f"{row['entity']} {row['uid'][:12]}", row["kept"], replaced)
    console.print(table)
    console.print("`myai sync dismiss <id>` marks one as seen. The record is kept either way.")


@sync_app.command("dismiss")
def sync_dismiss(conflict_id: int, data_dir: DataDirOpt = None) -> None:
    """Stop showing a conflict. It stays in the record."""
    _call(_service(data_dir).post, f"/sync/conflicts/{conflict_id}/dismiss", {})
    console.print(f"Conflict {conflict_id} marked as seen. It is still in the record.")


@security_app.command("capabilities")
def security_capabilities(data_dir: DataDirOpt = None, as_json: JsonOpt = False) -> None:
    """Everything a client can be granted, and what each one actually means."""
    data = _call(_service(data_dir).get, "/security/capabilities")
    if as_json:
        return _emit_json(data)
    table = Table("Capability", "What it allows", "Your content?")
    for row in data:
        table.add_row(
            row["capability"],
            f"{row['title']} — {row['detail']}",
            "yes" if row["sensitive"] else "no",
        )
    console.print(table)
    console.print(
        "Anything marked 'yes' lets a program read or change something you wrote. "
        "A client is given only what you approve when you make its pairing code."
    )


@security_app.command("grant")
def security_grant(
    device_id: str,
    capability: Annotated[
        list[str] | None,
        typer.Option("--can", help="A capability to allow. Repeat for several."),
    ] = None,
    preset: Annotated[
        str, typer.Option(help="'default', 'mobile' or 'full' instead of listing them.")
    ] = "",
    data_dir: DataDirOpt = None,
) -> None:
    """Replace what a client may do. What you do not list is taken away."""
    svc = _service(data_dir)
    if preset:
        known = {
            "default": ["status:read", "skills:read", "models:read"],
            "mobile": [
                "status:read",
                "skills:read",
                "models:read",
                "chat:read",
                "chat:write",
                "memory:read",
                "sync",
            ],
            "full": [row["capability"] for row in _call(svc.get, "/security/capabilities")],
        }
        wanted = known.get(preset.lower())
        if wanted is None:
            err_console.print(
                f"[red]Unknown preset '{preset}'. One of: default, mobile, full.[/red]"
            )
            raise typer.Exit(code=2)
    else:
        wanted = list(capability or [])
    data = _call(
        svc.request,
        "PUT",
        f"/security/devices/{device_id}/capabilities",
        json={"capabilities": wanted},
    )
    allowed = data["capabilities"]
    console.print(
        f"{data['name']} may now: " + (", ".join(allowed) if allowed else "nothing at all.")
    )


@portable_app.command("write")
def portable_write(
    destination: Annotated[
        str, typer.Option("--to", help="Where to write it. Omit to use this installation's folder.")
    ] = "",
    lock: Annotated[
        bool, typer.Option("--lock/--no-lock", help="Ask for a password and encrypt the package.")
    ] = False,
    data_dir: DataDirOpt = None,
    as_json: JsonOpt = False,
) -> None:
    """Write a .myai package of this AI: identity, memories, conversations, skills."""
    password = ""
    if lock:
        password = typer.prompt(
            "Password for this package", hide_input=True, confirmation_prompt=True
        )
    data = _call(
        _service(data_dir).post,
        "/portable",
        {"destination": destination, "password": password},
    )
    if as_json:
        return _emit_json(data)
    lines = [
        f"Wrote {data['path']}",
        f"{data['size_bytes'] / 1_000_000:.1f} MB · "
        + ("locked with a password" if data["encrypted"] else "not encrypted"),
        "",
        *(f"• {note}" for note in data["notes"]),
    ]
    console.print(
        Panel("\n".join(lines), title=f"Portable package — {data['manifest']['ai_name']}")
    )


@portable_app.command("inspect")
def portable_inspect(path: str, data_dir: DataDirOpt = None, as_json: JsonOpt = False) -> None:
    """Say whether a file is a MyAI package, and whether it needs a password."""
    data = _call(_service(data_dir).get, "/portable/inspect", path=path)
    if as_json:
        return _emit_json(data)
    if not data["is_package"]:
        console.print(f"[red]{data.get('detail', 'Not a MyAI package.')}[/red]")
        raise typer.Exit(code=1)
    lock = "needs a password" if data["needs_password"] else "not encrypted"
    console.print(f"A MyAI package, {lock}.")


@portable_app.command("preview")
def portable_preview(path: str, data_dir: DataDirOpt = None, as_json: JsonOpt = False) -> None:
    """What is in a package, and what of it will run on this machine. Changes nothing."""
    svc = _service(data_dir)
    password = ""
    if _call(svc.get, "/portable/inspect", path=path).get("needs_password"):
        password = typer.prompt("Password for this package", hide_input=True)
    data = _call(svc.post, "/portable/preview", {"path": path, "password": password})
    if as_json:
        return _emit_json(data)

    table = Table("What", "Here", "Detail")
    for cap in data["capabilities"]:
        table.add_row(cap["name"], cap["verdict"].replace("_", " "), cap["detail"])
    console.print(
        Panel(
            f"{data['ai_name']}, written by version {data['exported_by']} on "
            f"{data['exported_at']}.\n\n"
            f"Importing would REPLACE the AI on this machine"
            + (f" ({data['replaces_ai']})." if data["replaces_ai"] else "."),
            title="Portable package",
        )
    )
    console.print(table)
    for warning in data["warnings"]:
        console.print(f"[yellow]{warning}[/yellow]")


@portable_app.command("import")
def portable_import(path: str, data_dir: DataDirOpt = None) -> None:
    """Replace this installation's AI with the one in a package."""
    svc = _service(data_dir)
    password = ""
    if _call(svc.get, "/portable/inspect", path=path).get("needs_password"):
        password = typer.prompt("Password for this package", hide_input=True)
    preview = _call(svc.post, "/portable/preview", {"path": path, "password": password})

    console.print(
        "This replaces the AI on this machine"
        + (f" ({preview['replaces_ai']})" if preview["replaces_ai"] else "")
        + f" with {preview['ai_name']}. It cannot be undone."
    )
    typed = typer.prompt(f"Type {preview['confirmation_phrase']} to continue")
    if typed != preview["confirmation_phrase"]:
        console.print("Nothing was changed.")
        raise typer.Exit(code=1)

    data = _call(
        svc.post,
        "/portable/import",
        {"path": path, "password": password, "confirm": typed},
    )
    console.print(f"Restored {sum(data['rows_written'].values())} records.")
    for note in data["notes"]:
        console.print(f"  • {note}")


def entrypoint() -> None:
    """Console-script entry. A frozen CLI binary doubles as the benchmark sandbox host."""
    import sys

    from myai_core.skills.sandbox import SANDBOX_FLAG, harness_main

    if sys.argv[1:2] == [SANDBOX_FLAG]:
        raise SystemExit(harness_main())
    app()


if __name__ == "__main__":
    entrypoint()


# --- projects ---------------------------------------------------------------------------------


@projects_app.command("list")
def projects_list(
    data_dir: DataDirOpt = None,
    as_json: JsonOpt = False,
    archived: bool = typer.Option(False, "--archived", help="Include archived projects."),
) -> None:
    """List your projects and how much is filed under each."""
    svc = _service(data_dir)
    items = _call(svc.get, f"/projects?include_archived={'true' if archived else 'false'}")
    if as_json:
        return _emit_json(items)
    if not items:
        console.print('No projects yet. [dim]myai projects new "Kitchen rebuild"[/dim] makes one.')
        return
    table = Table(title="Projects")
    table.add_column("Name")
    table.add_column("Items", justify="right")
    table.add_column("Id", style="dim")
    for project in items:
        held = _call(svc.get, f"/projects/{project['id']}/contents")
        name = (
            f"{project['name']} [dim](archived)[/dim]" if project["archived"] else project["name"]
        )
        table.add_row(name, str(held["total"]), project["id"])
    console.print(table)


@projects_app.command("new")
def projects_new(
    name: str,
    description: str = typer.Option("", "--description", "-d"),
    data_dir: DataDirOpt = None,
) -> None:
    """Create a project."""
    project = _call(
        _service(data_dir).post, "/projects", {"name": name, "description": description}
    )
    console.print(f"[green]Created {project['name']}[/green] [dim]{project['id']}[/dim]")


@projects_app.command("archive")
def projects_archive(
    project_id: str,
    restore: bool = typer.Option(False, "--restore", help="Bring it back instead."),
    data_dir: DataDirOpt = None,
) -> None:
    """Put a project away, or bring it back. Nothing filed under it is touched."""
    project = _call(
        _service(data_dir).post, f"/projects/{project_id}/archive", {"archived": not restore}
    )
    word = "restored" if restore else "archived"
    console.print(f"[green]{project['name']} {word}[/green]")


@projects_app.command("delete")
def projects_delete(
    project_id: str,
    contents: str = typer.Option(
        ...,
        "--contents",
        help="keep: unfile them and leave them alone. delete: remove them too, permanently.",
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation."),
    data_dir: DataDirOpt = None,
) -> None:
    """Delete a project, saying what should happen to what is filed under it.

    `--contents` is required and has no default. This is the one command here that can
    destroy work, and the difference between the two answers is everything filed under the
    project, so it is not a flag anybody should be able to leave off and find out later.
    """
    if contents not in ("keep", "delete"):
        err_console.print("--contents must be 'keep' or 'delete'.")
        raise typer.Exit(code=2)

    svc = _service(data_dir)
    project = _call(svc.get, f"/projects/{project_id}")
    held = _call(svc.get, f"/projects/{project_id}/contents")

    if contents == "delete" and held["total"]:
        console.print(
            f"[red]This deletes {project['name']} and {held['total']} item(s) with it: "
            f"{held['conversations']} conversation(s), {held['memories']} memory(ies), "
            f"{held['documents']} document(s). This cannot be undone.[/red]"
        )
    else:
        console.print(
            f"Deleting {project['name']}. Its {held['total']} item(s) will be kept and simply "
            "stop belonging to a project."
        )
    if not yes and not typer.confirm("Go ahead?", default=False):
        raise typer.Exit(code=1)

    removed = _call(svc.post, f"/projects/{project_id}/delete", {"contents": contents})
    if contents == "delete":
        console.print(f"[green]Deleted, with {removed['total']} item(s).[/green]")
    else:
        console.print(f"[green]Deleted. {removed['total']} item(s) kept.[/green]")
