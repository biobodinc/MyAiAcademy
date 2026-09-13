"""Every practice task must be solvable exactly as written.

Training selects on these tasks, so a task that cannot be satisfied is worse than useless:
it caps what training can find and makes an honest search look like a failure. The
reference answers below are what a correct model would say; each has to score full marks.
"""

from __future__ import annotations

from myai_core.skills import graders
from myai_core.skills.packages import bundled_package, bundled_skill_ids

REFERENCE_ANSWERS: dict[str, dict[str, str]] = {
    "conversation": {
        "only-done": "DONE",
        "four-seasons": "- Spring\n- Summer\n- Autumn\n- Winter",
        "capital-japan": "Tokyo",
        "age-recall": "You are 41 years old.",
        "lowercase-only": "april",
        "true-false": "True",
        "count-down": "5 4 3 2 1",
        "pet-recall": "Biscuit",
        "french-morning": "Bonjour",
        "json-book": '{"title": "Orbit", "pages": 240}',
        "explain-password": (
            "A password is a secret word or phrase you keep to yourself to prove who you are "
            "before a system lets you in."
        ),
        "repeat-exactly": "Sixty zippers were quickly picked from the woven jute bag.",
    },
    "writing": {
        "three-line-poem": (
            "The sea keeps its own counsel\nand answers every question\nwith another wave."
        ),
        "forest-sentence": (
            "Under the pine canopy the silence held, broken only by needles falling."
        ),
        "future-tense": "He will cook dinner.",
        "fix-grammar": "She doesn't like apples.",
        "library-headline": "City Opens Library On Mill Street",
        "tea-steps": "1. Boil water\n2. Add a tea bag\n3. Pour the water\n4. Wait four minutes",
        "expand": (
            "The train we had been waiting for all afternoon finally arrived well behind its "
            "scheduled time."
        ),
        "no-very-cold": "Frost stiffened the grass and my breath hung in the still air.",
        "split-sentence": "The rain stopped. The children went outside.",
        "title-and-line": "Lost Tabby Cat\nA grey cat slipped out on Tuesday and has not returned.",
        "stronger-verb": "She strode into the room.",
        "blanket-blurb": (
            "Woven from soft lambswool, this blanket holds warmth without weight. The close "
            "weave resists pilling, the edges are bound by hand, and the natural fibre breathes, "
            "so it suits a cool evening indoors or a bright morning outside."
        ),
    },
    "science": {
        "multiply-2": "437",
        "divide-2": "32",
        "percent-2": "40",
        "m-to-cm": "320",
        "minutes-to-seconds": "240",
        "f-to-celsius": "20",
        "car-time": "3",
        "larger-fraction": "2/3",
        "freezing-point": "0",
        "why-seasons": (
            "Earth's axis is tilted, so each hemisphere leans toward the Sun for part of the "
            "year and away for the rest, changing the sunlight it receives."
        ),
        "octagon": "8",
        "prime-51": "No",
    },
    "research": {
        "bridge-year": "1954",
        "bridge-engineer": "Rosa Lindqvist",
        "bridge-vehicles": "12,000",
        "bridge-summary": (
            "The Calder Bridge, completed in 1954 by Rosa Lindqvist, carries 12,000 vehicles a "
            "day and was repainted in 2018."
        ),
        "bridge-unsupported": "No",
        "log-ferry": "Ferry log",
        "log-weather": "Weather log",
        "vegetables": "leek, kale",
        "yeast": "7 g",
        "three-facts": (
            "- Wind turbines generate electricity from moving air\n"
            "- They produce less power on calm days\n"
            "- Grid batteries store surplus energy"
        ),
        "not-stated-phone": "Not stated.",
        "order-years": "1962, 1985, 2009",
    },
    "games": {
        "two-mechanics": (
            "- Water a plant: costs one canful, and the plant grows a stage\n"
            "- Open a vent: allowed in daylight, and the greenhouse cools by five degrees"
        ),
        "lose-condition-short": "You lose when the fire goes out before sunrise.",
        "arrow-arithmetic": "9",
        "stamina-arithmetic": "4",
        "core-verb": "Climb",
        "spec-as-json-two": ('{"name": "Greenhouse", "genre": "simulation", "players": "2"}'),
        "curve-three-levels": (
            "- Level one teaches the basic move in a safe room\n"
            "- Level two adds a single hazard to avoid\n"
            "- Level three combines the move and the hazard under time pressure"
        ),
        "one-new-demand-two": "Diving underwater",
        "practice-before-block": (
            "A short corridor of slow enemies whose attacks the player can block without "
            "risk of dying."
        ),
        "room-count-arithmetic": "32",
        "hook-greenhouse": (
            "The greenhouse has been growing without you, and something in it is waiting."
        ),
        "remove-the-word-amazing": (
            "A remarkable game with inventive puzzles in a beautiful garden."
        ),
    },
    "coding": {
        "multiply-fn": "```python\ndef multiply(a, b):\n    return a * b\n```",
        "is-even": "```python\ndef is_even(n):\n    return n % 2 == 0\n```",
        "word-count-fn": "```python\ndef word_count(s):\n    return len(s.split())\n```",
        "largest": (
            "```python\ndef largest(nums):\n    if not nums:\n        return None\n"
            "    return max(nums)\n```"
        ),
        "unique-sorted": "```python\ndef unique_sorted(nums):\n    return sorted(set(nums))\n```",
        "fix-total": "```python\ndef total(nums):\n    return sum(nums)\n```",
        "fix-biggest": "```python\ndef biggest(nums):\n    return max(nums)\n```",
        "fix-count": (
            "```python\ndef count(items, target):\n    n = 0\n    for item in items:\n"
            "        if item == target:\n            n += 1\n    return n\n```"
        ),
        "print-slice": "bcd",
        "print-sorted": "1",
        "set-vs-list": "set",
        "safe-divide": (
            '```python\ndef safe_divide(a, b):\n    """Return a / b, or None when b is 0."""\n'
            "    if b == 0:\n        return None\n    return a / b\n```"
        ),
    },
}


def test_every_bundled_package_has_a_practice_set() -> None:
    for skill_id in bundled_skill_ids():
        package = bundled_package(skill_id)
        assert package is not None
        assert package.practice is not None, skill_id
        assert len(package.practice.tasks) >= 8, skill_id
        assert package.practice.tactics, skill_id


def test_practice_tasks_never_overlap_the_benchmark() -> None:
    """The level is measured on tasks training never selects against (see ADR-0013)."""
    for skill_id in bundled_skill_ids():
        package = bundled_package(skill_id)
        assert package is not None and package.practice is not None
        benchmark_ids = {t.id for t in package.benchmark.tasks}
        benchmark_prompts = {t.prompt.strip() for t in package.benchmark.tasks}
        for task in package.practice.tasks:
            assert task.id not in benchmark_ids, (skill_id, task.id)
            assert task.prompt.strip() not in benchmark_prompts, (skill_id, task.id)


def test_reference_answers_score_full_marks_on_every_practice_task() -> None:
    for skill_id in bundled_skill_ids():
        package = bundled_package(skill_id)
        assert package is not None and package.practice is not None
        answers = REFERENCE_ANSWERS[skill_id]
        assert set(answers) == {t.id for t in package.practice.tasks}, skill_id
        for task in package.practice.tasks:
            score, results = graders.grade(task.checks, answers[task.id], task.prompt)
            assert score == 1.0, (skill_id, task.id, [r.detail for r in results])


def test_tactics_are_short_enough_to_be_instructions() -> None:
    from myai_core.skills.training import TACTIC_MAX_CHARS

    for skill_id in bundled_skill_ids():
        package = bundled_package(skill_id)
        assert package is not None and package.practice is not None
        for tactic in package.practice.tactics:
            assert 8 <= len(tactic) <= TACTIC_MAX_CHARS, (skill_id, tactic)
