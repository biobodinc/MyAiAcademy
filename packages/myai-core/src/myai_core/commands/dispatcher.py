"""Execute parsed commands against Phase 1 services.

Every command that depends on a later phase returns ``UNAVAILABLE`` with a plain
explanation. Nothing here pretends to learn, train, remember or pause anything.
"""

from __future__ import annotations

from collections.abc import Callable

from myai_core.commands.models import (
    CommandName,
    CommandOutcome,
    CommandResult,
    ParsedCommand,
    TrainTarget,
)
from myai_core.commands.parser import CommandParseError, parse
from myai_core.guide import ask
from myai_core.hardware.models import HardwareReport
from myai_core.preferences.schemas import Preferences
from myai_core.skills.catalog import get_skill
from myai_core.skills.jobs import JobSummary
from myai_core.skills.learning import EvaluationRead, LearnPreview
from myai_core.skills.service import SkillsSummary
from myai_core.skills.trainer import TrainPreview

GiB = 1024**3
GUIDE_MIN_CONFIDENCE = 0.5

HELP_TEXT = """Commands you can use:

/learn <skill>      preview a new skill; "/learn <skill> start" installs it and runs its benchmark
/train <skill>      practise a skill you have learned (add '2h', 'level 60', an area or 'all')
/skills             list skills and levels
/status             AI, internet, jobs and training status
/hardware           what your computer can do
/memory             what I remember
/history            benchmark history: every level change and why
/pause /resume /stop  control the running job
/projects           list your projects
/settings           open settings
/help               this list

Plain sentences like "teach yourself video" map to these commands and I'll show you which."""


class CommandContext:
    """Lazy accessors so a ``/help`` never triggers a hardware scan.

    The Phase 3 callables are optional so the dispatcher stays usable in tests and in
    contexts without a job runner; when absent the commands say the feature is
    unavailable rather than pretending.
    """

    def __init__(
        self,
        *,
        hardware: Callable[[], HardwareReport],
        skills: Callable[[], SkillsSummary],
        preferences: Callable[[], Preferences],
        status: Callable[[], dict[str, object]],
        memories: Callable[[], list[str]] | None = None,
        projects: Callable[[], list[tuple[str, int]]] | None = None,
        learn_preview: Callable[[str], LearnPreview] | None = None,
        start_learn: Callable[[str], JobSummary] | None = None,
        current_job: Callable[[], JobSummary | None] | None = None,
        job_action: Callable[[str, str], bool] | None = None,
        history: Callable[[], list[EvaluationRead]] | None = None,
        train_preview: Callable[[str, TrainTarget | None], TrainPreview] | None = None,
        start_train: Callable[[str, TrainTarget | None], JobSummary] | None = None,
    ) -> None:
        self.hardware = hardware
        self.skills = skills
        self.preferences = preferences
        self.status = status
        self.memories = memories or (lambda: [])
        self.projects = projects
        self.learn_preview = learn_preview
        self.start_learn = start_learn
        self.current_job = current_job
        self.job_action = job_action
        self.history = history
        self.train_preview = train_preview
        self.start_train = start_train


def execute(text: str, ctx: CommandContext) -> CommandResult:
    try:
        cmd = parse(text)
    except CommandParseError as exc:
        return CommandResult(
            outcome=CommandOutcome.ERROR,
            command=None,
            title="Could not understand that command",
            message=str(exc),
            suggestions=["/help"],
        )
    if cmd is None:
        guide = ask(text)
        if guide.matched and guide.confidence >= GUIDE_MIN_CONFIDENCE:
            return CommandResult(
                outcome=CommandOutcome.OK,
                command=None,
                title=f"Guide: {guide.title}",
                message=guide.answer,
                data={"source": "guide", "topic_id": guide.topic_id},
                suggestions=[r.question for r in guide.related][:3],
            )
        return CommandResult(
            outcome=CommandOutcome.UNAVAILABLE,
            command=None,
            title="That is a message for your AI",
            message=(
                "Plain messages go to the local model in Chat. This console runs slash "
                "commands and answers questions about MyAI Academy itself: try /help."
            ),
            data={"navigate": "/chat"},
            suggestions=["/help", "/status", "What is training?"],
        )
    handler = _HANDLERS.get(cmd.name, _unavailable)
    return handler(cmd, ctx)


def _help(cmd: ParsedCommand, _ctx: CommandContext) -> CommandResult:
    return CommandResult(outcome=CommandOutcome.OK, command=cmd, title="Help", message=HELP_TEXT)


def _status(cmd: ParsedCommand, ctx: CommandContext) -> CommandResult:
    data = ctx.status()
    lines = [
        f"🧠 AI: {data.get('ai_label', 'unknown')}",
        f"🌐 Internet: {data.get('internet_label', 'unknown')}",
        f"📚 Job: {data.get('job_label', 'unknown')}",
        f"🎓 Training: {data.get('training_label', 'unknown')}",
    ]
    return CommandResult(
        outcome=CommandOutcome.OK, command=cmd, title="Status", message="\n".join(lines), data=data
    )


def _hardware(cmd: ParsedCommand, ctx: CommandContext) -> CommandResult:
    report = ctx.hardware()
    gpu = report.primary_gpu
    gpu_line = (
        f"{gpu.name} ({(gpu.vram_total_bytes or 0) / GiB:.1f} GiB VRAM, {gpu.backend})"
        if gpu
        else "none detected"
    )
    ram = (report.memory.total_bytes or 0) / GiB
    message = "\n".join(
        [
            f"OS: {report.os.system} {report.os.release or ''}".strip(),
            f"CPU: {report.cpu.model_name or 'unknown'} "
            f"({report.cpu.physical_cores or '?'} cores / "
            f"{report.cpu.logical_threads or '?'} threads)",
            f"RAM: {ram:.0f} GiB",
            f"GPU: {gpu_line}",
            f"Tier: {report.tier.tier.value.title()} (estimate from specifications)",
        ]
    )
    return CommandResult(
        outcome=CommandOutcome.OK,
        command=cmd,
        title="Your hardware",
        message=message,
        data={"tier": report.tier.tier.value, "warnings": report.warnings},
    )


def _skills(cmd: ParsedCommand, ctx: CommandContext) -> CommandResult:
    summary = ctx.skills()
    rows = []
    for s in summary.skills:
        if s.learned:
            state = f"Level {s.level}"
        elif not s.learnable:
            state = f"Not learnable yet (Phase {s.planned_phase})"
        elif s.locked:
            state = s.locked_reason or "Locked"
        else:
            state = f"Not learned: /learn {s.id}"
        rows.append(f"{s.icon} {s.name:<13} {state}")
    message = f"Overall level {summary.overall_level}\n\n" + "\n".join(rows)
    return CommandResult(
        outcome=CommandOutcome.OK,
        command=cmd,
        title="Skills",
        message=message,
        data={"overall_level": summary.overall_level},
    )


def _settings(cmd: ParsedCommand, ctx: CommandContext) -> CommandResult:
    prefs = ctx.preferences()
    return CommandResult(
        outcome=CommandOutcome.OK,
        command=cmd,
        title="Settings",
        message=(
            f"Mode: {prefs.experience_mode.value}\n"
            f"Compute: {prefs.compute_preset.value}\n"
            f"Theme: {prefs.theme.value}\n"
            f"Privacy: {prefs.privacy_mode.value} (contributor mode "
            f"{'on' if prefs.contributor_mode else 'off'})"
        ),
        data={"navigate": "/settings"},
    )


def _memory(cmd: ParsedCommand, ctx: CommandContext) -> CommandResult:
    items = ctx.memories()
    if not items:
        message = (
            "I don't remember anything yet. Add memories on the Memory page; I never "
            "remember conversations on my own."
        )
    else:
        shown = items[:20]
        message = "\n".join(f"• {m}" for m in shown)
        if len(items) > len(shown):
            message += f"\n… and {len(items) - len(shown)} more."
    return CommandResult(
        outcome=CommandOutcome.OK,
        command=cmd,
        title=f"Memory ({len(items)})",
        message=message,
        data={"count": len(items), "navigate": "/memory"},
    )


def _projects(cmd: ParsedCommand, ctx: CommandContext) -> CommandResult:
    """List projects and how much is filed under each.

    Read-only on purpose. Creating a project is harmless, but this console's other
    destructive verb — deleting one — needs a question about its contents that a single
    line of text cannot ask safely, so both live where that question can be put properly.
    """
    if ctx.projects is None:
        return _unavailable(cmd, ctx)

    items = ctx.projects()
    if not items:
        message = (
            "No projects yet. A project groups the conversations, memories and files that "
            "belong to one piece of work. Create one on the Projects page."
        )
    else:
        message = "\n".join(
            f"• {name} — {count} item{'' if count == 1 else 's'}" for name, count in items[:20]
        )
        if len(items) > 20:
            message += f"\n… and {len(items) - 20} more."
    return CommandResult(
        outcome=CommandOutcome.OK,
        command=cmd,
        title=f"Projects ({len(items)})",
        message=message,
        data={"count": len(items), "navigate": "/projects"},
    )


def _learn(cmd: ParsedCommand, ctx: CommandContext) -> CommandResult:
    if cmd.skill is None:
        return _unknown_skill(cmd)
    skill = get_skill(cmd.skill)
    assert skill is not None
    if ctx.learn_preview is None or ctx.start_learn is None:
        return CommandResult(
            outcome=CommandOutcome.UNAVAILABLE,
            command=cmd,
            title="Learning is not available here",
            message="This console cannot start jobs. Use the Skills page or `myai skills learn`.",
        )
    preview = ctx.learn_preview(skill.id)
    if preview.already_learned:
        return CommandResult(
            outcome=CommandOutcome.OK,
            command=cmd,
            title=f"{skill.icon} {skill.name} is already learned",
            message=(
                f"Re-run its benchmark with the Skills page or `myai skills evaluate {skill.id}`, "
                f"or improve it once training arrives: /train {skill.id}"
            ),
            suggestions=["/skills", f"/train {skill.id}"],
        )
    if preview.blockers:
        return CommandResult(
            outcome=CommandOutcome.UNAVAILABLE,
            command=cmd,
            title=f"{skill.icon} {skill.name} cannot be learned yet",
            message="\n".join(preview.blockers),
            data={"navigate": "/skills"},
            suggestions=["/skills", "/hardware"],
        )
    wants_start = any(a.lower() in {"start", "confirm", "yes", "go"} for a in cmd.args[1:])
    if not wants_start:
        return CommandResult(
            outcome=CommandOutcome.OK,
            command=cmd,
            title=f"{skill.icon} New skill: {skill.name}",
            message=_learn_preview_text(preview),
            data={"preview": preview.model_dump(mode="json")},
            suggestions=[f"/learn {skill.id} start", "/skills"],
        )
    job = ctx.start_learn(skill.id)
    return CommandResult(
        outcome=CommandOutcome.OK,
        command=cmd,
        title=f"{skill.icon} Learning {skill.name}",
        message=(
            f"Package installed. Running the {skill.name} benchmark with your local model; "
            f"the level it scores becomes {skill.name}'s level. The skill counts as learned "
            "only when the benchmark finishes. Follow progress with /status."
        ),
        data={"job": job.model_dump(mode="json"), "navigate": "/skills"},
        suggestions=["/status", "/pause", "/stop"],
    )


def _learn_preview_text(preview: LearnPreview) -> str:
    package = preview.package
    assert package is not None
    if preview.estimated_minutes_min is not None and preview.estimated_minutes_max is not None:
        estimate = (
            f"{preview.estimated_minutes_min:g}-{preview.estimated_minutes_max:g} minutes "
            f"({preview.estimate_note})"
        )
    else:
        estimate = f"unknown ({preview.estimate_note})"
    return "\n".join(
        [
            preview.what_happens,
            "",
            f"Resources required: {package.size_bytes / 1024:.0f} KB ({package.resources})",
            f"Benchmark: {package.task_count} tasks across {', '.join(package.areas)}",
            f"Model: {preview.model_id}",
            f"Recommended compute: {preview.recommended_compute.value}",
            f"Estimated learning preparation: {estimate}",
            "",
            "Start learning? Reply with: /learn " + preview.skill_id + " start",
        ]
    )


def _train(cmd: ParsedCommand, ctx: CommandContext) -> CommandResult:
    if cmd.skill is None:
        return _unknown_skill(cmd)
    skill = get_skill(cmd.skill)
    assert skill is not None
    current = next((s for s in ctx.skills().skills if s.id == skill.id), None)
    if current is None or not current.learned:
        return CommandResult(
            outcome=CommandOutcome.UNAVAILABLE,
            command=cmd,
            title=f"You haven't learned {skill.name} yet",
            message=f"Learn it first with /learn {skill.id}; training improves what is there.",
            suggestions=[f"/learn {skill.id}"],
        )
    if ctx.train_preview is None or ctx.start_train is None:
        return CommandResult(
            outcome=CommandOutcome.UNAVAILABLE,
            command=cmd,
            title=f"{skill.icon} Training {skill.name} is not available here",
            message="This build has no job runner, so nothing can be trained from it.",
            suggestions=["/skills"],
        )
    preview = ctx.train_preview(skill.id, cmd.train)
    if preview.blockers:
        return CommandResult(
            outcome=CommandOutcome.UNAVAILABLE,
            command=cmd,
            title=f"{skill.icon} {skill.name} cannot be trained yet",
            message="\n".join(preview.blockers),
            data={"navigate": "/skills"},
            suggestions=["/skills", f"/learn {skill.id}"],
        )
    wants_start = any(a.lower() in {"start", "confirm", "yes", "go"} for a in cmd.args[1:])
    if not wants_start:
        return CommandResult(
            outcome=CommandOutcome.OK,
            command=cmd,
            title=f"{skill.icon} Training {skill.name}",
            message=_train_preview_text(preview),
            data={"preview": preview.model_dump(mode="json")},
            suggestions=[f"/train {skill.id} start", "/skills"],
        )
    job = ctx.start_train(skill.id, cmd.train)
    return CommandResult(
        outcome=CommandOutcome.OK,
        command=cmd,
        title=f"{skill.icon} Training {skill.name}",
        message=(
            f"Practising for about {preview.budget_minutes:g} minutes. Each change is kept "
            f"only if it scores better on practice tasks, and at the end the {skill.name} "
            "benchmark decides whether the result is kept at all. Follow progress with "
            "/status; /pause, /resume and /stop control it."
        ),
        data={"job": job.model_dump(mode="json"), "navigate": "/skills"},
        suggestions=["/status", "/pause", "/stop"],
    )


def _train_preview_text(preview: TrainPreview) -> str:
    if preview.estimated_rounds_min is not None and preview.estimated_rounds_max is not None:
        rounds = (
            f"{preview.estimated_rounds_min}-{preview.estimated_rounds_max} rounds "
            f"({preview.estimate_note})"
        )
    else:
        rounds = f"unknown ({preview.estimate_note})"
    areas = [
        f"{k.replace('_', ' ')}: {round(v * 100)}%" for k, v in preview.last_area_scores.items()
    ]
    lines = [
        preview.what_happens,
        "",
        f"Current level: {preview.current_level}",
        f"Target level: {preview.target_level or preview.recommended_target}"
        + (
            ""
            if preview.target_level
            else f" (recommended; add 'level {preview.recommended_target}')"
        ),
        "Last benchmark by area: " + (", ".join(areas) if areas else "none yet"),
        preview.focus_note,
        f"Time budget: {preview.budget_minutes:g} minutes. {preview.budget_note}",
        f"Practice tasks: {preview.search_tasks} to search with, {preview.check_tasks} to confirm "
        f"with, out of {preview.practice_tasks}. The benchmark is separate and untouched.",
        f"Estimated: {rounds}",
        f"Model: {preview.model_id}",
    ]
    if preview.resume_rounds:
        lines.append(
            f"Continuing from an earlier run that completed {preview.resume_rounds} rounds."
        )
    lines += ["", f"Start training? Reply with: /train {preview.skill_id} start"]
    return "\n".join(lines)


def _job_control(cmd: ParsedCommand, ctx: CommandContext) -> CommandResult:
    action = {
        CommandName.PAUSE: "pause",
        CommandName.RESUME: "resume",
        CommandName.STOP: "cancel",
    }[cmd.name]
    job = ctx.current_job() if ctx.current_job else None
    if job is None or ctx.job_action is None:
        return CommandResult(
            outcome=CommandOutcome.UNAVAILABLE,
            command=cmd,
            title="No job is running",
            message="There is nothing to " + cmd.name.value + ". Start one with /learn <skill>.",
            suggestions=["/skills"],
        )
    ok = ctx.job_action(job.id, action)
    verb = {"pause": "paused", "resume": "resumed", "cancel": "stopping"}[action]
    if not ok:
        return CommandResult(
            outcome=CommandOutcome.ERROR,
            command=cmd,
            title=f"Could not {cmd.name.value} that job",
            message=f"The {job.kind} job for {job.skill_id} is {job.status}.",
            suggestions=["/status"],
        )
    return CommandResult(
        outcome=CommandOutcome.OK,
        command=cmd,
        title=f"Job {verb}",
        message=f"{job.kind.title()} {job.skill_id.title()} at {job.progress_percent}% is {verb}.",
        data={"job_id": job.id},
        suggestions=["/status"],
    )


def _history(cmd: ParsedCommand, ctx: CommandContext) -> CommandResult:
    rows = ctx.history() if ctx.history else []
    if not rows:
        return CommandResult(
            outcome=CommandOutcome.OK,
            command=cmd,
            title="History",
            message="No benchmark runs yet. Levels only ever change through them.",
            suggestions=["/skills"],
        )
    lines = [
        f"{r.evaluated_at:%b %d %H:%M}  {r.skill_id.title():<13} {r.level_before:>3} → "
        f"{r.level_after:<3} ({round(r.score * 100)}% with {r.model_id})"
        for r in rows[:20]
    ]
    return CommandResult(
        outcome=CommandOutcome.OK,
        command=cmd,
        title="Benchmark history",
        message="\n".join(lines),
        data={"navigate": "/skills"},
    )


def _unknown_skill(cmd: ParsedCommand) -> CommandResult:
    return CommandResult(
        outcome=CommandOutcome.ERROR,
        command=cmd,
        title=f"I don't know a skill called '{cmd.skill_text}'",
        message="Use /skills to see what can be learned.",
        suggestions=["/skills"],
    )


def _unavailable(cmd: ParsedCommand, _ctx: CommandContext) -> CommandResult:
    phase = {CommandName.PROJECTS: 7}.get(cmd.name)
    return CommandResult(
        outcome=CommandOutcome.UNAVAILABLE,
        command=cmd,
        title=f"/{cmd.name.value} is not available yet",
        message=(
            f"This command is planned for Phase {phase}."
            if phase
            else "Not available in this build."
        ),
        suggestions=["/help"],
    )


_HANDLERS: dict[CommandName, Callable[[ParsedCommand, CommandContext], CommandResult]] = {
    CommandName.HELP: _help,
    CommandName.STATUS: _status,
    CommandName.HARDWARE: _hardware,
    CommandName.SKILLS: _skills,
    CommandName.SETTINGS: _settings,
    CommandName.MEMORY: _memory,
    CommandName.PROJECTS: _projects,
    CommandName.LEARN: _learn,
    CommandName.TRAIN: _train,
    CommandName.PAUSE: _job_control,
    CommandName.RESUME: _job_control,
    CommandName.STOP: _job_control,
    CommandName.HISTORY: _history,
}
