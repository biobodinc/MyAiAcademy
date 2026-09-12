"""Training end to end over the API, with a scripted model.

The model is scripted to follow exactly one rule: when that rule is in its instructions it
answers correctly, and otherwise it does not. That makes the assertions about training
sharp — if training works, it finds the rule, the benchmark improves and the result is
kept; if the rule cannot help, nothing is kept and the run says so.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from myai_core.api.app import create_app
from myai_core.config import CoreSettings
from myai_core.db.models import (
    AIProfile,
    InstalledModel,
    SkillEvaluation,
    SkillState,
    TrainingRun,
)
from myai_core.models.llama_cpp_provider import LlamaCppProvider
from myai_core.paths import AppPaths
from myai_core.skills.packages import TRAINED, bundled_package
from myai_core.skills.trainer import TrainingService, TrainPreview
from myai_core.skills.training import Candidate, RoundRecord, TrainingPlan

from .test_practice_sets import REFERENCE_ANSWERS

TOKEN = "t"
RULE = "When a number only is asked for, give digits with no words and no units."
VAGUE = "I am not certain, but it is probably somewhere around four hundred or so."

SCIENCE_BENCHMARK_ANSWERS = {
    "multiply": "391",
    "divide": "12",
    "percent": "30",
    "km-to-m": "2500",
    "hours-to-minutes": "90",
    "celsius-to-f": "212",
    "train-distance": "150 km",
    "larger-decimal": "0.5",
    "boiling-point": "100",
    "blue-sky": (
        "Sunlight scatters off air molecules and blue wavelengths scatter most, so blue "
        "light reaches your eyes from all over the sky."
    ),
    "hexagon": "6",
    "prime": "Yes",
}


class ScriptedLlama:
    """Correct only while RULE is in the system prompt. Writes RULE when asked for a rule."""

    follows_rule = True
    writes_rule = True

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    def create_chat_completion(self, **kwargs: Any) -> Iterator[dict[str, Any]]:
        messages = kwargs["messages"]
        prompt = messages[-1]["content"]
        system = messages[0]["content"]
        reply = self._reply(system, prompt)
        if ScriptedLlama.delay:
            time.sleep(ScriptedLlama.delay)
        yield {"choices": [{"delta": {"content": reply}, "finish_reason": None}]}
        yield {"choices": [{"delta": {}, "finish_reason": "stop"}]}

    def _reply(self, system: str, prompt: str) -> str:
        if "Write one short rule" in prompt:
            return RULE if ScriptedLlama.writes_rule else "Try harder next time"
        package = bundled_package("science")
        assert package is not None and package.practice is not None
        informed = ScriptedLlama.follows_rule and RULE in system
        for task in package.practice.tasks:
            if task.prompt == prompt:
                return REFERENCE_ANSWERS["science"][task.id] if informed else VAGUE
        for task in package.benchmark.tasks:
            if task.prompt == prompt:
                return SCIENCE_BENCHMARK_ANSWERS[task.id] if informed else VAGUE
        return "Hello."


@pytest.fixture
def client(app_paths: AppPaths, tmp_path: Path) -> Iterator[TestClient]:
    ScriptedLlama.follows_rule = True
    ScriptedLlama.writes_rule = True
    ScriptedLlama.delay = 0.0
    provider = LlamaCppProvider(llama_factory=ScriptedLlama)
    app = create_app(CoreSettings(), app_paths, token=TOKEN, provider=provider)
    with TestClient(app, base_url="http://127.0.0.1") as c:
        c.headers.update({"Authorization": f"Bearer {TOKEN}"})
        c.post("/api/profile", json={"name": "Nova"})
        c.put("/api/storage/root", json={"root_path": str(tmp_path / "MyAI")})
        _install_model(c, tmp_path)
        yield c


def _install_model(client: TestClient, tmp_path: Path) -> None:
    path = tmp_path / "MyAI" / "Models" / "m.gguf"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * 2048)
    state = client.app.state.core  # type: ignore[attr-defined]
    with state.session_factory() as session:
        session.add(
            InstalledModel(
                id="m",
                display_name="M",
                family="f",
                file_path=str(path),
                size_bytes=2048,
                license_id="apache-2.0",
            )
        )
        session.commit()
    client.post("/api/models/active", json={"model_id": "m"})


def _ai_id(session: Session) -> str:
    profile = session.scalars(select(AIProfile)).first()
    assert profile is not None
    return profile.ai_id


def _plan(client: TestClient, seed: int = 1) -> TrainingPlan:
    """The plan the service builds for the default preview, used to seed a run directly."""
    preview = TrainPreview.model_validate(
        client.post("/api/skills/science/train-preview", json={}).json()
    )
    state = client.app.state.core  # type: ignore[attr-defined]
    with state.session_factory() as session:
        return TrainingService(session, _ai_id(session)).plan(preview, seed=seed)


def _a_round(change: str) -> RoundRecord:
    return RoundRecord(
        index=1,
        source="package",
        change=change,
        search_score=0.8,
        check_score=0.8,
        accepted=True,
        seconds=0.1,
    )


def _wait_job(client: TestClient, job_id: str, timeout: float = 60.0) -> dict[str, Any]:
    state = client.app.state.core  # type: ignore[attr-defined]
    state.jobs.wait(job_id, timeout)
    return client.get(f"/api/jobs/{job_id}").json()


def _learn(client: TestClient) -> dict[str, Any]:
    """Learn Science, including the prerequisites the skill tree requires first."""
    result: dict[str, Any] = {}
    for skill_id in ("conversation", "research", "science"):
        started = client.post(f"/api/skills/{skill_id}/learn")
        assert started.status_code == 202, started.text
        result = _wait_job(client, started.json()["id"])
        assert result["status"] == "completed", result.get("error")
    return result


def _train(client: TestClient, **request: Any) -> dict[str, Any]:
    body = {"duration_seconds": 60, "all_areas": True, **request}
    started = client.post("/api/skills/science/train", json=body)
    assert started.status_code == 202, started.text
    return _wait_job(client, started.json()["id"])


# --- preview --------------------------------------------------------------------------------


def test_preview_refuses_an_unlearned_skill_and_starts_nothing(client: TestClient) -> None:
    res = client.post("/api/skills/science/train-preview", json={})
    assert res.status_code == 200
    preview = res.json()
    assert preview["trainable"] is False
    assert any("Learn Science first" in b for b in preview["blockers"])
    assert client.post("/api/skills/science/train", json={}).status_code == 409
    assert client.get("/api/jobs/current").json() is None


def test_preview_explains_the_plan_it_would_run(client: TestClient) -> None:
    _learn(client)
    preview = client.post(
        "/api/skills/science/train-preview", json={"duration_seconds": 1800}
    ).json()
    assert preview["trainable"] is True and preview["blockers"] == []
    assert preview["budget_minutes"] == 30
    assert preview["search_tasks"] + preview["check_tasks"] == preview["practice_tasks"]
    assert preview["focus_area"] in preview["areas"]  # defaults to the weakest area
    assert "weakest area" in preview["focus_note"]
    assert "weights are not changed" in preview["what_happens"]


def test_an_unknown_focus_area_is_reported_rather_than_silently_ignored(
    client: TestClient,
) -> None:
    _learn(client)
    preview = client.post(
        "/api/skills/science/train-preview", json={"specialization": "poetry"}
    ).json()
    assert preview["focus_area"] is None
    assert "not one of this skill's areas" in preview["focus_note"]


# --- the training job -----------------------------------------------------------------------


def test_training_improves_the_skill_and_the_benchmark_decides(
    client: TestClient, tmp_path: Path
) -> None:
    learned = _learn(client)
    level_after_learning = learned["result"]["level_after"]

    job = _train(client)
    assert job["status"] == "completed", job.get("error")
    result = job["result"]
    assert result["applied"] is True
    assert result["benchmark_after"] > result["benchmark_before"]
    assert result["level_after"] > level_after_learning
    assert result["rounds"] >= 1 and result["accepted_rounds"] >= 1
    assert "benchmark went from" in result["summary"]

    # The level came from an evaluation row, as it always must (ADR-0007).
    state = client.app.state.core  # type: ignore[attr-defined]
    with state.session_factory() as session:
        run = session.get(TrainingRun, result["training_run_id"])
        assert run is not None and run.status == "applied" and run.applied is True
        evaluation = session.get(SkillEvaluation, run.evaluation_id)
        assert evaluation is not None
        assert evaluation.level_after == result["level_after"]
        assert evaluation.job_id == job["id"]
        skill_state = session.scalars(
            select(SkillState).where(SkillState.skill_id == "science")
        ).first()
        assert skill_state is not None and skill_state.trained_at is not None

    # The trained instructions are on disk beside the package and reach the chat prompt.
    trained = list((tmp_path / "MyAI" / "Skills" / "science").rglob(TRAINED))
    assert trained, "training claimed to apply instructions but wrote none"
    assert RULE in trained[0].read_text(encoding="utf-8")


def test_nothing_is_kept_when_the_model_ignores_its_instructions(client: TestClient) -> None:
    _learn(client)
    ScriptedLlama.follows_rule = False
    ScriptedLlama.writes_rule = False

    job = _train(client)
    result = job["result"]
    assert result["applied"] is False
    assert result["accepted_rounds"] == 0
    assert "nothing that scored better" in result["summary"]
    state = client.app.state.core  # type: ignore[attr-defined]
    with state.session_factory() as session:
        run = session.get(TrainingRun, result["training_run_id"])
        assert run is not None and run.status == "kept_previous"
        # The benchmark still ran, so the level is still a measured number.
        assert session.get(SkillEvaluation, run.evaluation_id) is not None


def test_a_training_run_records_every_round_it_tried(client: TestClient) -> None:
    _learn(client)
    job = _train(client)
    runs = client.get("/api/skills/science/training").json()
    assert len(runs) == 1
    run = runs[0]
    assert run["rounds_completed"] == len(run["rounds"]) >= 1
    assert all(r["change"] for r in run["rounds"])
    assert any(r["accepted"] for r in run["rounds"])
    assert run["job_id"] == job["id"]
    assert run["finished_at"] is not None


def test_only_one_job_runs_at_a_time(client: TestClient) -> None:
    _learn(client)
    first = client.post("/api/skills/science/train", json={"duration_seconds": 60})
    assert first.status_code == 202
    second = client.post("/api/skills/science/train", json={"duration_seconds": 60})
    assert second.status_code == 409
    _wait_job(client, first.json()["id"])


def test_stopping_a_training_job_leaves_the_skill_as_it_was(client: TestClient) -> None:
    before = _learn(client)["result"]["level_after"]
    # Stopping can only be tested against a job that is still running. With an instant
    # model a whole run finishes before the cancel request lands, so the model is slowed
    # for this test; without that the assertion is a race that fails on a fast machine.
    ScriptedLlama.delay = 0.02
    started = client.post("/api/skills/science/train", json={"duration_seconds": 60}).json()
    for _ in range(400):
        if client.get(f"/api/jobs/{started['id']}").json()["progress_done"] > 0:
            break
        time.sleep(0.05)
    client.post(f"/api/jobs/{started['id']}/cancel")
    job = _wait_job(client, started["id"])
    assert job["status"] == "cancelled"
    skill = client.get("/api/skills/science").json()
    assert skill["level"] == before
    assert skill["trained_at"] is None


# --- checkpoints and recovery ----------------------------------------------------------------


def test_an_interrupted_run_keeps_its_best_instructions_for_next_time(
    client: TestClient,
) -> None:
    """What a crash leaves behind is the point of checkpointing (spec §40, §74)."""
    _learn(client)
    plan = _plan(client)
    state = client.app.state.core  # type: ignore[attr-defined]
    with state.session_factory() as session:
        service = TrainingService(session, _ai_id(session))
        run = service.begin(
            "science", job_id="job_x", model_id="m", package_version="1.0.0", plan=plan
        )
        service.record_round(run.id, _a_round(f"Added guidance: {RULE}"), Candidate(tactics=[RULE]))
        session.commit()
        run_id = run.id

    # A restart marks it interrupted without throwing away what it found.
    with state.session_factory() as session:
        service = TrainingService(session, _ai_id(session))
        assert service.recover() == 1
        session.commit()
        stale = session.get(TrainingRun, run_id)
        assert stale is not None and stale.status == "interrupted"
        assert "continues from them" in stale.summary
        resumed = service.resume_candidate("science", "1.0.0")
        assert resumed is not None and resumed.tactics == [RULE]

    preview = client.post("/api/skills/science/train-preview", json={}).json()
    assert preview["resume_rounds"] == 1


def test_a_candidate_from_a_different_package_version_is_not_resumed(
    client: TestClient,
) -> None:
    """Instructions built for one package must not be carried onto another."""
    _learn(client)
    plan = _plan(client)
    state = client.app.state.core  # type: ignore[attr-defined]
    with state.session_factory() as session:
        service = TrainingService(session, _ai_id(session))
        run = service.begin(
            "science", job_id=None, model_id="m", package_version="0.9.0", plan=plan
        )
        service.record_round(run.id, _a_round("stale"), Candidate(tactics=["stale rule"]))
        session.commit()
        assert service.resume_candidate("science", "1.0.0") is None


# --- undoing --------------------------------------------------------------------------------


def test_reverting_restores_the_package_instructions_and_keeps_the_measured_level(
    client: TestClient, tmp_path: Path
) -> None:
    _learn(client)
    result = _train(client)["result"]
    assert result["applied"] is True
    level = client.get("/api/skills/science").json()["level"]

    reverted = client.post("/api/skills/science/training/revert")
    assert reverted.status_code == 200
    assert reverted.json()["trained_at"] is None
    assert reverted.json()["level"] == level  # reverting measures nothing, so it changes nothing
    assert not list((tmp_path / "MyAI" / "Skills" / "science").rglob(TRAINED))
    # A second revert has nothing to undo and says so rather than pretending.
    assert client.post("/api/skills/science/training/revert").status_code == 409


def test_the_users_time_limit_is_the_ceiling_on_a_training_budget(client: TestClient) -> None:
    """The advanced compute time limit is enforced, not merely stored (spec §31)."""
    _learn(client)
    client.patch("/api/preferences", json={"time_limit_minutes": 5})
    preview = client.post(
        "/api/skills/science/train-preview", json={"duration_seconds": 3600}
    ).json()
    assert preview["budget_minutes"] == 5
    assert "time limit of 5 minutes" in preview["budget_note"]

    client.patch("/api/preferences", json={"time_limit_minutes": None})
    preview = client.post(
        "/api/skills/science/train-preview", json={"duration_seconds": 3600}
    ).json()
    assert preview["budget_minutes"] == 60
