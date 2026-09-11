"""``myai`` command-line interface (Typer)."""

from __future__ import annotations

import json
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
app.add_typer(storage_app, name="storage")
app.add_typer(profile_app, name="profile")
app.add_typer(models_app, name="models")
app.add_typer(memory_app, name="memory")
app.add_typer(knowledge_app, name="knowledge")
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
    console.print(
        Panel(
            "\n".join(
                [
                    internet,
                    ai,
                    training,
                    f"🔒 Privacy mode: {data['privacy_mode']}  "
                    f"(cloud uploads: {data['cloud_uploads']})",
                    f"Service v{data['service_version']}",
                ]
            ),
            title="MyAI status",
        )
    )


@app.command()
def hardware(
    data_dir: DataDirOpt = None,
    refresh: Annotated[bool, typer.Option(help="Re-run detection.")] = False,
    as_json: JsonOpt = False,
) -> None:
    """Show detected hardware and the estimated capability tier."""
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
        state = (
            "learned"
            if s["learned"]
            else (
                "locked: " + s["locked_reason"]
                if s["locked"]
                else f"not learned (Phase {s['planned_phase']})"
            )
        )
        table.add_row(f"{s['icon']} {s['name']}", str(s["level"]), s["band"], state)
    console.print(table)


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


if __name__ == "__main__":
    app()
