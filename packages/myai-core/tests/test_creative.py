"""Creative skills: the one that is real, and the three that say why they are not.

Games is a learnable skill because designing mechanics, levels and narrative is prose and
arithmetic — the same thing the text benchmarks already measure. Images, video and music
need something that produces pixels or audio, which this build has none of.

The temptation these tests guard against is the easy version: call a cloud API, call it
done. That would be the single clearest break of what this program tells people it does,
so the refusal is tested rather than assumed.
"""

from __future__ import annotations

import inspect
from pathlib import Path

from myai_core.skills import creative, graders
from myai_core.skills.catalog import SkillAvailability, get_skill
from myai_core.skills.creative import Medium, all_statuses, provider_for, status
from myai_core.skills.packages import bundled_package, bundled_skill_ids


def test_games_is_a_real_skill_with_a_real_benchmark() -> None:
    skill = get_skill("games")
    assert skill is not None
    assert skill.availability is SkillAvailability.AVAILABLE
    assert "games" in bundled_skill_ids()

    package = bundled_package("games")
    assert package is not None
    assert len(package.benchmark.tasks) >= 10
    assert package.practice is not None and len(package.practice.tasks) >= 10
    assert set(package.manifest.areas) == {"mechanics", "level design", "narrative"}


def test_every_games_benchmark_task_is_graded_by_a_machine_not_an_opinion() -> None:
    """A level has to mean something. Nothing here is scored by asking a model if it liked it."""
    package = bundled_package("games")
    assert package is not None
    deterministic = {
        "bullets",
        "word_count",
        "line_count",
        "numeric",
        "regex",
        "exact",
        "contains_all",
        "contains_any",
        "contains_none",
        "json_object",
        "python_tests",
        "code_contains",
    }
    for task in (*package.benchmark.tasks, *(package.practice.tasks if package.practice else ())):
        assert task.checks, task.id
        for check in task.checks:
            assert check["type"] in deterministic, (task.id, check["type"])


def test_the_games_benchmark_covers_every_area_it_claims() -> None:
    package = bundled_package("games")
    assert package is not None
    areas = {task.area for task in package.benchmark.tasks}
    assert areas == set(package.manifest.areas)


def test_a_wrong_answer_actually_fails() -> None:
    """A benchmark that passes everything measures nothing."""
    package = bundled_package("games")
    assert package is not None
    task = next(t for t in package.benchmark.tasks if t.id == "damage-arithmetic")
    score, _results = graders.grade(task.checks, "about seven or so", task.prompt)
    assert score < 1.0

    counted = next(t for t in package.benchmark.tasks if t.id == "three-mechanics")
    score, _results = graders.grade(counted.checks, "- only one bullet", counted.prompt)
    assert score < 1.0


# --------------------------------------------------------------------------------------
# The three that cannot run here.
# --------------------------------------------------------------------------------------


def test_no_provider_is_installed_and_nothing_pretends_otherwise() -> None:
    for medium in Medium:
        assert provider_for(medium) is None
        report = status(medium)
        assert report.available is False
        assert medium.value in report.detail
        assert report.needs, f"{medium} does not say what it would take"


def test_every_medium_says_it_will_not_be_sent_to_an_online_service() -> None:
    """The easy version of this feature is a cloud API. It is refused in words, on purpose."""
    for report in all_statuses():
        assert "online service" in report.detail
        assert "locally" in report.needs or "local" in report.needs.lower()


def test_nothing_in_the_creative_module_reaches_the_network() -> None:
    """A file about generating media is exactly where a quiet HTTP call would hide."""
    source = Path(inspect.getfile(creative)).read_text(encoding="utf-8")
    body = "\n".join(
        line for line in source.splitlines() if not line.strip().startswith(("*", "#"))
    )
    for forbidden in ("httpx", "requests", "urllib", "socket", "aiohttp", "http://", "https://"):
        assert forbidden not in body, f"{forbidden} appears in the creative provider module"


def test_a_creative_skill_says_what_it_needs_rather_than_naming_a_phase() -> None:
    """'Planned for Phase 10' tells someone nothing they can act on."""
    from myai_core.skills.learning import _no_package_reason

    images = get_skill("images")
    assert images is not None
    reason = _no_package_reason(images)
    assert "Phase" not in reason
    assert "graphics card" in reason or "gigabytes" in reason
    assert "online service" in reason

    # A non-creative planned skill still falls back to the phase, which is the honest
    # answer for one that is only waiting on a benchmark.
    conversation = get_skill("conversation")
    assert conversation is not None


def test_the_provider_protocol_is_what_a_real_one_would_have_to_satisfy() -> None:
    """Written down now so a later implementation has something to conform to."""
    for name in ("name", "medium", "availability", "generate"):
        assert hasattr(creative.CreativeProvider, name), name
