"""Turn ``"/train video 4h"`` or ``"teach yourself video"`` into a :class:`ParsedCommand`."""

from __future__ import annotations

import re
import shlex

from myai_core.commands.models import CommandName, ParsedCommand, TrainTarget
from myai_core.skills.catalog import resolve_skill_id

_DURATION_RE = re.compile(r"^(\d+(?:\.\d+)?)(h|hr|hrs|hour|hours|m|min|mins|minute|minutes)$", re.I)
_LEVEL_RE = re.compile(r"^(?:level|lvl|l)(\d{1,3})$", re.I)

_SKILL_COMMANDS = {CommandName.LEARN, CommandName.TRAIN}

# Natural-language triggers (spec §81). Kept intentionally small and literal: the goal is to
# recognise obvious phrasings and *show* the user which command they map to, not to be
# an NLU system. Anything unrecognised is left for the chat model (Phase 2).
_NL_PATTERNS: tuple[tuple[re.Pattern[str], CommandName], ...] = (
    (
        re.compile(
            r"^(?:teach yourself|learn|acquire)\s+(?:the\s+)?(?P<skill>[a-z]+)\s*(?:skill)?[.!]?$",
            re.I,
        ),
        CommandName.LEARN,
    ),
    (
        re.compile(
            r"^(?:train|practice|practise|improve)\s+(?:your\s+)?(?P<skill>[a-z]+)\s*(?:skill)?(?P<rest>.*)$",
            re.I,
        ),
        CommandName.TRAIN,
    ),
    (re.compile(r"^(?:show|list)\s+(?:me\s+)?(?:your\s+)?skills[.!?]?$", re.I), CommandName.SKILLS),
    (re.compile(r"^(?:what(?:'s| is) your|show|check)\s+status[.!?]?$", re.I), CommandName.STATUS),
    (re.compile(r"^(?:what|which)\s+hardware\b.*$", re.I), CommandName.HARDWARE),
    (
        re.compile(r"^(?:what do you remember|show (?:your )?memory)[.!?]?$", re.I),
        CommandName.MEMORY,
    ),
    (re.compile(r"^(?:pause|stop)\s+training[.!?]?$", re.I), CommandName.PAUSE),
    (re.compile(r"^resume\s+training[.!?]?$", re.I), CommandName.RESUME),
)


class CommandParseError(ValueError):
    pass


def is_command(text: str) -> bool:
    return text.strip().startswith("/")


def parse(text: str) -> ParsedCommand | None:
    """Parse a message. Returns ``None`` when it is plain chat for the model."""
    stripped = text.strip()
    if not stripped:
        return None
    if stripped.startswith("/"):
        return _parse_slash(stripped)
    return _parse_natural(stripped)


def _parse_slash(text: str) -> ParsedCommand:
    try:
        tokens = shlex.split(text[1:])
    except ValueError as exc:  # unbalanced quotes
        raise CommandParseError(f"Could not parse command: {exc}") from exc
    if not tokens:
        raise CommandParseError("Empty command. Try /help.")
    head, *rest = tokens
    try:
        name = CommandName(head.lower())
    except ValueError as exc:
        raise CommandParseError(f"Unknown command '/{head}'. Try /help.") from exc
    return _build(name, text, rest, natural=False)


def _parse_natural(text: str) -> ParsedCommand | None:
    for pattern, name in _NL_PATTERNS:
        m = pattern.match(text)
        if not m:
            continue
        rest: list[str] = []
        skill = m.groupdict().get("skill")
        if skill:
            rest.append(skill)
        extra = m.groupdict().get("rest")
        if extra:
            rest.extend(_nl_rest_tokens(extra))
        return _build(name, text, rest, natural=True)
    return None


def _nl_rest_tokens(extra: str) -> list[str]:
    """``"for 4 hours"`` → ``["4h"]``; ``"to level 10"`` → ``["level", "10"]``."""
    words = extra.replace(",", " ").split()
    out: list[str] = []
    i = 0
    while i < len(words):
        w = words[i].lower().strip(".!?")
        nxt = words[i + 1].lower().strip(".!?") if i + 1 < len(words) else ""
        if w.isdigit() and nxt in {"hours", "hour", "h", "hrs"}:
            out.append(f"{w}h")
            i += 2
        elif w.isdigit() and nxt in {"minutes", "minute", "min", "mins", "m"}:
            out.append(f"{w}m")
            i += 2
        elif w in {"level", "lvl"} and nxt.isdigit():
            out.extend(["level", nxt])
            i += 2
        elif w in {"for", "to", "the", "a", "an", "on", "in"}:
            i += 1
        else:
            out.append(w)
            i += 1
    return out


def _build(name: CommandName, raw: str, rest: list[str], *, natural: bool) -> ParsedCommand:
    cmd = ParsedCommand(name=name, raw=raw, args=rest, natural_language=natural)
    if name not in _SKILL_COMMANDS:
        return cmd
    if not rest:
        raise CommandParseError(f"/{name.value} needs a skill, e.g. /{name.value} video.")
    cmd.skill_text = rest[0]
    cmd.skill = resolve_skill_id(rest[0])
    if name is CommandName.TRAIN:
        cmd.train = _parse_train_target(rest[1:])
    return cmd


def _parse_train_target(tokens: list[str]) -> TrainTarget:
    target = TrainTarget()
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        low = tok.lower()
        if low == "all":
            target.all_areas = True
            i += 1
            continue
        duration = _DURATION_RE.match(tok)
        if duration:
            amount = float(duration.group(1))
            unit = duration.group(2).lower()
            seconds = amount * 3600 if unit.startswith("h") else amount * 60
            target.duration_seconds = int(seconds)
            i += 1
            continue
        if low in {"level", "lvl"} and i + 1 < len(tokens) and tokens[i + 1].isdigit():
            target.target_level = _level(tokens[i + 1])
            i += 2
            continue
        level = _LEVEL_RE.match(tok)
        if level:
            target.target_level = _level(level.group(1))
            i += 1
            continue
        if target.specialization is None:
            target.specialization = low
        else:
            target.specialization = f"{target.specialization} {low}"
        i += 1
    return target


def _level(text: str) -> int:
    value = int(text)
    if not 1 <= value <= 100:
        raise CommandParseError("Levels run from 1 to 100.")
    return value
