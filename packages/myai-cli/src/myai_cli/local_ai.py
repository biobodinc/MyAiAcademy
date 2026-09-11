"""CLI commands for Phase 2: models, chat, memory and knowledge."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Annotated, Any

import httpx
import typer
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from myai_cli.client import ApiError, LocalService, ServiceNotRunningError
from myai_cli.format import human_bytes, percent_bar

console = Console()
err_console = Console(stderr=True)

models_app = typer.Typer(
    help="Local models: catalog, licences, downloads, activation.", no_args_is_help=True
)
memory_app = typer.Typer(help="What your AI remembers.", no_args_is_help=True)
knowledge_app = typer.Typer(help="Documents your AI can retrieve from.", no_args_is_help=True)

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


# --- models ---------------------------------------------------------------------------------


@models_app.command("list")
def models_list(data_dir: DataDirOpt = None, as_json: JsonOpt = False) -> None:
    """Show the catalog with install state, licences and hardware fit."""
    data = _call(_service(data_dir).get, "/models")
    if as_json:
        return _emit_json(data)
    runtime = "ready" if data["runtime_available"] else f"unavailable ({data['runtime_detail']})"
    table = Table(title=f"Models — runtime {runtime}")
    table.add_column("Id")
    table.add_column("Name")
    table.add_column("Size", justify="right")
    table.add_column("Licence")
    table.add_column("Fit")
    table.add_column("State")
    for m in data["models"]:
        c = m["catalog"] or {}
        size = c.get("approx_size_bytes") or m.get("size_bytes")
        fit = "recommended" if m["fit"]["recommended"] else ("ok" if m["fit"]["ok"] else "too big")
        if m["active"]:
            state = "[green]active[/green]"
        elif m["installed"]:
            state = "installed"
        elif m["download"]:
            d = m["download"]
            state = f"{d['status']} {human_bytes(d['bytes_done'])}"
        else:
            state = "licence accepted" if m["license_accepted"] else "—"
        table.add_row(
            m["id"],
            m["name"] + (" (imported)" if m["source"] == "imported" else ""),
            human_bytes(size),
            m["license"]["name"],
            fit,
            state,
        )
    console.print(table)


@models_app.command("show")
def models_show(model_id: str, data_dir: DataDirOpt = None) -> None:
    """Show a model's description, licence and fit reasons."""
    data = _call(_service(data_dir).get, "/models")
    entry = next((m for m in data["models"] if m["id"] == model_id), None)
    if entry is None:
        err_console.print(f"[red]Unknown model '{model_id}'.[/red]")
        raise typer.Exit(code=1)
    c = entry["catalog"]
    lic = entry["license"]
    if c is None:
        console.print(
            Panel(
                "\n".join(
                    [
                        f"{entry['name']}  (imported)",
                        entry["description"],
                        f"Size: {human_bytes(entry['size_bytes'])}  sha256 {entry['file_sha256']}",
                        entry["verification_detail"] or "",
                        f"Licence: {lic['name']} — {lic['summary']}",
                        *[f"  • {r}" for r in entry["fit"]["reasons"]],
                    ]
                ),
                title=entry["id"],
            )
        )
        return
    lines = [
        f"{c['name']}  ({c['parameters_billion']}B, {c['quantization']}, "
        f"context {c['context_length']})",
        c["description"],
        "",
        f"Source: https://huggingface.co/{c['hf_repo']}  file {c['hf_filename']}",
        f"Approx. size: {human_bytes(c['approx_size_bytes'])}; "
        f"needs ~{human_bytes(c['min_ram_bytes'])} RAM",
        "",
        f"Licence: {lic['name']}  ({lic['url']})",
        f"  {lic['summary']}",
        f"  Commercial use: {lic['commercial_use']}",
        "",
        f"Verification: {entry['verification_detail'] or 'not installed yet'}",
        "",
        "Fit: "
        + (
            "recommended"
            if entry["fit"]["recommended"]
            else "ok"
            if entry["fit"]["ok"]
            else "does not fit"
        ),
        *[f"  • {r}" for r in entry["fit"]["reasons"]],
    ]
    console.print(Panel("\n".join(lines), title=c["id"]))


@models_app.command("download")
def models_download(
    model_id: str,
    data_dir: DataDirOpt = None,
    accept_license: Annotated[
        bool, typer.Option("--accept-license", help="Confirm you have read and accept the licence.")
    ] = False,
) -> None:
    """Accept the licence (after showing it) and download a model with progress."""
    svc = _service(data_dir)
    models_show(model_id, data_dir)
    if not accept_license:
        accept_license = typer.confirm("Do you accept this licence?", default=False)
    if not accept_license:
        console.print("Not downloaded.")
        raise typer.Exit(code=1)
    _call(svc.post, f"/models/{model_id}/accept-license", {})
    job = _call(svc.request, "POST", f"/models/{model_id}/download")
    console.print(f"Download started ({job['id']}).")
    with Live(console=console, refresh_per_second=4) as live:
        while True:
            job = _call(svc.get, f"/models/downloads/{job['id']}")
            total = job["bytes_total"]
            frac = job["bytes_done"] / total if total else 0
            live.update(
                f"{percent_bar(frac, 30)} {human_bytes(job['bytes_done'])} / "
                f"{human_bytes(total) if total else '?'}  [{job['status']}]"
            )
            if job["status"] in {"completed", "failed", "cancelled"}:
                break
            time.sleep(0.5)
    if job["status"] == "completed":
        console.print(
            f"[green]Installed and verified.[/green] Make it active: myai models use {model_id}"
        )
    else:
        err_console.print(f"[red]{job['status']}: {job.get('error') or ''}[/red]")
        raise typer.Exit(code=1)


@models_app.command("use")
def models_use(model_id: str, data_dir: DataDirOpt = None) -> None:
    """Make an installed model the active one."""
    _call(_service(data_dir).post, "/models/active", {"model_id": model_id})
    console.print(f"[green]{model_id} is now active.[/green]")


@models_app.command("import")
def models_import(
    path: str,
    name: Annotated[
        str | None, typer.Option(help="Display name (defaults to the file name).")
    ] = None,
    confirm_rights: Annotated[
        bool,
        typer.Option(
            "--confirm-rights",
            help="Confirm you may use this file under its licence. Required.",
        ),
    ] = False,
    data_dir: DataDirOpt = None,
) -> None:
    """Register a GGUF file you already have. Files outside Models/ are copied in."""
    if not confirm_rights:
        err_console.print(
            "[red]Pass --confirm-rights to confirm you may use this model file under its "
            "licence. MyAI Academy does not verify licences for imported files.[/red]"
        )
        raise typer.Exit(code=1)
    data = _call(
        _service(data_dir).post,
        "/models/import",
        {"path": str(Path(path).expanduser().resolve()), "name": name, "rights_confirmed": True},
    )
    entry = next(m for m in data["models"] if m["source"] == "imported" and m["installed"])
    console.print(f"[green]Imported {entry['name']} as {entry['id']}[/green]  {entry['file_path']}")


@models_app.command("check")
def models_check(model_id: str, data_dir: DataDirOpt = None, as_json: JsonOpt = False) -> None:
    """Ask the file host what it declares for a model. Downloads nothing.

    Use this when a download fails its integrity check: it shows whether the publisher
    actually publishes a content hash for the file.
    """
    data = _call(_service(data_dir).get, f"/models/{model_id}/source")
    if as_json:
        return _emit_json(data)
    lines = [
        f"URL:        {data['url']}",
        f"Served by:  {data['final_url']}",
        f"Status:     {data['status_code']}",
        f"Size:       {human_bytes(data['size_bytes'])}",
        "",
        f"Publisher hash: {data['publisher_sha256'] or 'not published'}",
        f"Pinned hash:    {data['pinned_sha256'] or 'none in the catalog'}",
        f"Host ETag:      {data['etag_sha256'] or 'not a SHA-256'}  (advisory only)",
        "",
        data["note"],
    ]
    console.print(Panel("\n".join(lines), title=f"Source for {data['model_id']}"))


@models_app.command("providers")
def models_providers(data_dir: DataDirOpt = None, as_json: JsonOpt = False) -> None:
    """Show the model-provider tree and each provider's real status."""
    data = _call(_service(data_dir).get, "/models/providers")
    if as_json:
        return _emit_json(data)
    table = Table(title="Model providers")
    table.add_column("Provider")
    table.add_column("Kind")
    table.add_column("Status")
    table.add_column("Detail")
    for p in data:
        colour = {"available": "green", "unavailable": "red", "planned": "yellow"}[p["status"]]
        table.add_row(p["name"], p["kind"], f"[{colour}]{p['status']}[/{colour}]", p["detail"])
    console.print(table)


@models_app.command("unload")
def models_unload(data_dir: DataDirOpt = None) -> None:
    """Release the loaded model's memory; the next chat message loads it again."""
    data = _call(_service(data_dir).post, "/models/unload", {})
    console.print(
        "[green]Model unloaded.[/green]"
        if data["loaded_model_id"] is None
        else f"Still loaded: {data['loaded_model_id']}"
    )


@models_app.command("remove")
def models_remove(model_id: str, data_dir: DataDirOpt = None) -> None:
    """Delete a downloaded model file."""
    if not typer.confirm(f"Delete {model_id} from disk?", default=False):
        raise typer.Exit(code=1)
    _call(_service(data_dir).request, "DELETE", f"/models/{model_id}")
    console.print("Removed.")


# --- chat -----------------------------------------------------------------------------------


def chat(
    message: Annotated[
        str | None, typer.Argument(help="One message; omit for interactive mode.")
    ] = None,
    data_dir: DataDirOpt = None,
    conversation: Annotated[
        str | None,
        typer.Option("--conversation", "-c", help="Continue an existing conversation id."),
    ] = None,
) -> None:
    """Talk to your AI. Streams the reply; slash commands work too."""
    svc = _service(data_dir)
    if conversation is None:
        conversation = _call(svc.post, "/chat/conversations", {})["id"]
        console.print(f"[dim]conversation {conversation}[/dim]")
    if message is not None:
        _stream_turn(svc, conversation, message)
        return
    console.print("[dim]Interactive chat. Ctrl-D or /quit to leave.[/dim]")
    while True:
        try:
            text = console.input("[bold]you>[/bold] ")
        except (EOFError, KeyboardInterrupt):
            console.print()
            break
        if text.strip() in {"/quit", "/exit"}:
            break
        if text.strip():
            _stream_turn(svc, conversation, text)


def _stream_turn(svc: LocalService, conversation: str, text: str) -> None:
    url = f"{svc.api_base}/chat/conversations/{conversation}/messages"
    headers = {"Authorization": f"Bearer {svc.token}", "Accept": "text/event-stream"}
    try:
        with (
            httpx.Client(timeout=httpx.Timeout(None, connect=5.0)) as client,
            client.stream("POST", url, json={"content": text}, headers=headers) as response,
        ):
            if response.status_code >= 400:
                body = response.read().decode("utf-8", "replace")
                try:
                    detail = json.loads(body).get("detail", body)
                except ValueError:
                    detail = body
                err_console.print(f"[red]{response.status_code}: {detail}[/red]")
                raise typer.Exit(code=1)
            kind: str | None = None
            for line in response.iter_lines():
                if line.startswith("event: "):
                    kind = line[7:]
                elif line.startswith("data: ") and kind:
                    payload = json.loads(line[6:])
                    _render_event(kind, payload)
                    kind = None
    except httpx.HTTPError as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc


def _render_event(kind: str, payload: dict[str, Any]) -> None:
    if kind == "meta":
        retrieved = payload.get("retrieved") or []
        if retrieved:
            titles = sorted({r["document_title"] for r in retrieved})
            console.print(f"[dim]using knowledge: {', '.join(titles)}[/dim]")
        sys.stdout.write("ai> ")
        sys.stdout.flush()
    elif kind == "delta":
        sys.stdout.write(str(payload.get("text", "")))
        sys.stdout.flush()
    elif kind == "done":
        sys.stdout.write("\n")
        sys.stdout.flush()
        ms = payload.get("duration_ms")
        tokens = payload.get("completion_tokens")
        if ms is not None:
            rate = f", {tokens / (ms / 1000):.1f} tok/s" if tokens and ms else ""
            console.print(f"[dim]{ms} ms{rate}[/dim]")
    elif kind == "error":
        sys.stdout.write("\n")
        err_console.print(f"[red]{payload.get('message')}[/red]")
    elif kind == "command":
        console.print(Panel(str(payload.get("message", "")), title=str(payload.get("title", ""))))


# --- memory ---------------------------------------------------------------------------------


@memory_app.command("list")
def memory_list(
    data_dir: DataDirOpt = None,
    search: Annotated[str | None, typer.Option("--search", "-s")] = None,
    as_json: JsonOpt = False,
) -> None:
    """List (or search) memories."""
    data = _call(_service(data_dir).get, "/memory", q=search)
    if as_json:
        return _emit_json(data)
    if not data:
        console.print('Nothing remembered yet. Add one: myai memory add "..."')
        return
    table = Table(title="Memory")
    table.add_column("Id", justify="right")
    table.add_column("Category")
    table.add_column("Content")
    for m in data:
        table.add_row(str(m["id"]), m["category"], m["content"])
    console.print(table)


@memory_app.command("add")
def memory_add(
    content: str,
    data_dir: DataDirOpt = None,
    category: Annotated[str, typer.Option(help="fact, preference, instruction or other")] = "fact",
) -> None:
    """Remember something."""
    m = _call(_service(data_dir).post, "/memory", {"content": content, "category": category})
    console.print(f"[green]Remembered (#{m['id']}).[/green]")


@memory_app.command("forget")
def memory_forget(memory_id: int, data_dir: DataDirOpt = None) -> None:
    """Delete one memory."""
    _call(_service(data_dir).request, "DELETE", f"/memory/{memory_id}")
    console.print("Forgotten.")


@memory_app.command("clear")
def memory_clear(data_dir: DataDirOpt = None) -> None:
    """Delete every memory (asks first)."""
    if not typer.confirm("Delete ALL memories?", default=False):
        raise typer.Exit(code=1)
    result = _call(_service(data_dir).request, "DELETE", "/memory")
    console.print(f"Deleted {result['deleted']}.")


# --- knowledge ------------------------------------------------------------------------------


@knowledge_app.command("list")
def knowledge_list(data_dir: DataDirOpt = None, as_json: JsonOpt = False) -> None:
    """List documents in the knowledge library."""
    data = _call(_service(data_dir).get, "/knowledge")
    if as_json:
        return _emit_json(data)
    table = Table(
        title=f"Knowledge — {data['document_count']} documents, {data['chunk_count']} passages"
    )
    table.add_column("Id")
    table.add_column("Title")
    table.add_column("Type")
    table.add_column("Size", justify="right")
    table.add_column("Passages", justify="right")
    for d in data["documents"]:
        table.add_row(
            d["id"],
            d["title"],
            d["media_type"],
            human_bytes(d["size_bytes"]),
            str(d["chunk_count"]),
        )
    console.print(table)
    console.print(f"[dim]Retrieval: {data['retrieval_method']}[/dim]")


@knowledge_app.command("add")
def knowledge_add(
    paths: Annotated[list[Path], typer.Argument(help="Files to add (txt, md, pdf, code…).")],
    data_dir: DataDirOpt = None,
) -> None:
    """Add files to knowledge. This lets the AI retrieve them; it does not retrain anything."""
    svc = _service(data_dir)
    for path in paths:
        try:
            doc = svc.post("/knowledge/files", {"path": str(path.expanduser().resolve())})
            console.print(f"[green]{doc['title']}[/green]: {doc['chunk_count']} passages")
        except ApiError as exc:
            err_console.print(f"[red]{path}: {exc.detail}[/red]")


@knowledge_app.command("search")
def knowledge_search(query: str, data_dir: DataDirOpt = None) -> None:
    """Preview what the AI would retrieve for a question."""
    hits = _call(_service(data_dir).get, "/knowledge/search", q=query)
    if not hits:
        console.print("No matching passages.")
        return
    for h in hits:
        console.print(Panel(h["content"], title=f"{h['document_title']} §{h['ordinal'] + 1}"))


@knowledge_app.command("remove")
def knowledge_remove(document_id: str, data_dir: DataDirOpt = None) -> None:
    """Remove a document from knowledge."""
    _call(_service(data_dir).request, "DELETE", f"/knowledge/{document_id}")
    console.print("Removed.")
