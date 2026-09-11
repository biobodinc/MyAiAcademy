"""Execute parsed commands against Phase 1 services.

Every command that depends on a later phase returns ``UNAVAILABLE`` with a plain
explanation. Nothing here pretends to learn, train, remember or pause anything.
"""

from __future__ import annotations

from collections.abc import Callable

from myai_core.commands.models import CommandName, CommandOutcome, CommandResult, ParsedCommand
from myai_core.commands.parser import CommandParseError, parse
from myai_core.guide import ask
from myai_core.hardware.models import HardwareReport
from myai_core.preferences.schemas import Preferences
from myai_core.skills.catalog import get_skill
from myai_core.skills.service import SkillsSummary

GiB = 1024**3
GUIDE_MIN_CONFIDENCE = 0.5

HELP_TEXT = """Commands you can use:

/learn <skill>      acquire a new skill (Phase 3)
/train <skill>      improve a skill you already have (Phase 4)
/skills             list skills and levels
/status             AI, internet and training status
/hardware           what your computer can do
/memory             what I remember
/projects           your projects (Phase 7)
/history            training history (Phase 4)
/pause /resume /stop  control a training job (Phase 4)
/settings           open settings
/help               this list

Plain sentences like "teach yourself video" map to these commands and I'll show you which."""


class CommandContext:
    """Lazy accessors so a ``/help`` never triggers a hardware scan."""

    def __init__(
        self,
        *,
        hardware: Callable[[], HardwareReport],
        skills: Callable[[], SkillsSummary],
        preferences: Callable[[], Preferences],
        status: Callable[[], dict[str, object]],
        memories: Callable[[], list[str]] | None = None,
    ) -> None:
        self.hardware = hardware
        self.skills = skills
        self.preferences = preferences
        self.status = status
        self.memories = memories or (lambda: [])


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
        state = f"Level {s.level}" if s.learned else "Not learned"
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


def _learn(cmd: ParsedCommand, _ctx: CommandContext) -> CommandResult:
    if cmd.skill is None:
        return _unknown_skill(cmd)
    skill = get_skill(cmd.skill)
    assert skill is not None
    return CommandResult(
        outcome=CommandOutcome.UNAVAILABLE,
        command=cmd,
        title=f"{skill.icon} Learning {skill.name} is not available yet",
        message=(
            f"{skill.name} is in the catalog, but skill packages and the learning pipeline "
            f"arrive in Phase {skill.planned_phase}. Nothing has been downloaded or changed."
        ),
        suggestions=["/skills", "/hardware"],
    )


def _train(cmd: ParsedCommand, ctx: CommandContext) -> CommandResult:
    if cmd.skill is None:
        return _unknown_skill(cmd)
    skill = get_skill(cmd.skill)
    assert skill is not None
    summary = ctx.skills()
    status = next(s for s in summary.skills if s.id == skill.id)
    if not status.learned:
        return CommandResult(
            outcome=CommandOutcome.UNAVAILABLE,
            command=cmd,
            title=f"You haven't learned {skill.name} yet",
            message=f"Learn it first with /learn {skill.id}.",
            suggestions=[f"/learn {skill.id}"],
        )
    return CommandResult(
        outcome=CommandOutcome.UNAVAILABLE,
        command=cmd,
        title="Training is not available yet",
        message="Training jobs arrive in Phase 4. Nothing has started.",
        suggestions=["/skills"],
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
    phase = {
        CommandName.PAUSE: 4,
        CommandName.RESUME: 4,
        CommandName.STOP: 4,
        CommandName.HISTORY: 4,
        CommandName.PROJECTS: 7,
    }.get(cmd.name)
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
    CommandName.LEARN: _learn,
    CommandName.TRAIN: _train,
}
