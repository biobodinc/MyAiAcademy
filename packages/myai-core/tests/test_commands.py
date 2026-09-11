from __future__ import annotations

import pytest

from myai_core.commands.dispatcher import CommandContext, execute
from myai_core.commands.models import CommandName, CommandOutcome
from myai_core.commands.parser import CommandParseError, parse
from myai_core.hardware.models import CpuInfo, HardwareReport, MemoryInfo, OsInfo, TierEstimate
from myai_core.preferences.schemas import Preferences
from myai_core.skills.service import SkillsService


def test_plain_chat_is_not_a_command() -> None:
    assert parse("hello there") is None
    assert parse("") is None


def test_simple_commands() -> None:
    for text, name in [
        ("/help", CommandName.HELP),
        ("/status", CommandName.STATUS),
        ("/HARDWARE", CommandName.HARDWARE),
        ("  /skills  ", CommandName.SKILLS),
    ]:
        cmd = parse(text)
        assert cmd is not None and cmd.name is name


def test_unknown_command() -> None:
    with pytest.raises(CommandParseError, match="Unknown command"):
        parse("/frobnicate")


def test_learn_requires_skill() -> None:
    with pytest.raises(CommandParseError, match="needs a skill"):
        parse("/learn")


def test_learn_resolves_skill_and_keeps_unknown_text() -> None:
    cmd = parse("/learn Video")
    assert cmd and cmd.skill == "video" and cmd.skill_text == "Video"
    cmd = parse("/learn juggling")
    assert cmd and cmd.skill is None and cmd.skill_text == "juggling"


@pytest.mark.parametrize(
    ("text", "duration", "level", "spec", "all_areas"),
    [
        ("/train video", None, None, None, False),
        ("/train video 4h", 14400, None, None, False),
        ("/train video 90m", 5400, None, None, False),
        ("/train video 1.5h", 5400, None, None, False),
        ("/train video level 10", None, 10, None, False),
        ("/train video level10", None, 10, None, False),
        ("/train video cinematic", None, None, "cinematic", False),
        ("/train video all", None, None, None, True),
        ("/train video 4h level 10 cinematic", 14400, 10, "cinematic", False),
        ('/train video "camera movement"', None, None, "camera movement", False),
    ],
)
def test_train_qualifiers(
    text: str, duration: int | None, level: int | None, spec: str | None, all_areas: bool
) -> None:
    cmd = parse(text)
    assert cmd and cmd.train is not None
    assert cmd.train.duration_seconds == duration
    assert cmd.train.target_level == level
    assert cmd.train.specialization == spec
    assert cmd.train.all_areas is all_areas


def test_train_level_bounds() -> None:
    with pytest.raises(CommandParseError):
        parse("/train video level 500")


def test_natural_language_mapping() -> None:
    cmd = parse("Teach yourself video")
    assert cmd and cmd.name is CommandName.LEARN and cmd.skill == "video"
    assert cmd.natural_language is True
    cmd = parse("train your coding skill for 2 hours")
    assert cmd and cmd.name is CommandName.TRAIN and cmd.skill == "coding"
    assert cmd.train and cmd.train.duration_seconds == 7200
    cmd = parse("improve video to level 12")
    assert cmd and cmd.train and cmd.train.target_level == 12
    cmd = parse("show me your skills")
    assert cmd and cmd.name is CommandName.SKILLS
    assert parse("Tell me a story about a horse") is None


# --- dispatcher ---------------------------------------------------------------------------


def _ctx(session) -> CommandContext:  # type: ignore[no-untyped-def]
    report = HardwareReport(
        detected_at="2026-01-01T00:00:00Z",  # type: ignore[arg-type]
        os=OsInfo(system="TestOS"),
        cpu=CpuInfo(model_name="Test CPU", physical_cores=8, logical_threads=16),
        memory=MemoryInfo(total_bytes=32 * 1024**3),
        tier=TierEstimate(tier="capable", method="specification-estimate"),  # type: ignore[arg-type]
    )
    return CommandContext(
        hardware=lambda: report,
        skills=lambda: SkillsService(session).summary(None),
        preferences=Preferences,
        status=lambda: {"ai_label": "x", "internet_label": "Online", "training_label": "y"},
    )


def test_dispatch_help_and_hardware(session) -> None:  # type: ignore[no-untyped-def]
    ctx = _ctx(session)
    assert execute("/help", ctx).outcome is CommandOutcome.OK
    hw = execute("/hardware", ctx)
    assert hw.outcome is CommandOutcome.OK and "Test CPU" in hw.message
    assert "estimate" in hw.message


def test_dispatch_learn_is_honest_about_unavailability(session) -> None:  # type: ignore[no-untyped-def]
    res = execute("/learn video", _ctx(session))
    assert res.outcome is CommandOutcome.UNAVAILABLE
    assert "Nothing has been downloaded" in res.message


def test_dispatch_train_unlearned_offers_learn(session) -> None:  # type: ignore[no-untyped-def]
    res = execute("/train video 4h", _ctx(session))
    assert res.outcome is CommandOutcome.UNAVAILABLE
    assert res.suggestions == ["/learn video"]


def test_dispatch_unknown_skill(session) -> None:  # type: ignore[no-untyped-def]
    res = execute("/learn juggling", _ctx(session))
    assert res.outcome is CommandOutcome.ERROR


def test_dispatch_parse_error_and_chat(session) -> None:  # type: ignore[no-untyped-def]
    assert execute("/nope", _ctx(session)).outcome is CommandOutcome.ERROR
    chat = execute("hi nova", _ctx(session))
    assert chat.outcome is CommandOutcome.UNAVAILABLE and chat.command is None


def test_dispatch_later_phase_commands(session) -> None:  # type: ignore[no-untyped-def]
    for text in ("/pause", "/projects", "/history"):
        res = execute(text, _ctx(session))
        assert res.outcome is CommandOutcome.UNAVAILABLE
        assert "Phase" in res.message
