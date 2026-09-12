"""Learning a skill end to end with a scripted fake model: preview, job lifecycle with
pause/cancel, level only from the benchmark, history, degrees, prompt integration."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from myai_core.api.app import create_app
from myai_core.config import CoreSettings
from myai_core.db.models import InstalledModel
from myai_core.models.llama_cpp_provider import LlamaCppProvider
from myai_core.models.provider import LoadConfig
from myai_core.paths import AppPaths
from myai_core.skills.evaluate import JobCancelledError, JobControl, evaluate_package
from myai_core.skills.jobs import JobBusyError, JobManager
from myai_core.skills.packages import bundled_package

TOKEN = "t"

# Answers the fake model gives for the science benchmark: 8 of 12 fully right on purpose;
# 'blue-sky' earns half credit (word limit met, mechanism missing) -> 8.5/12.
SCIENCE_ANSWERS = {
    "multiply": "391",
    "divide": "12",
    "percent": "30",
    "km-to-m": "2500",
    "hours-to-minutes": "90",
    "celsius-to-f": "212",
    "train-distance": "150",
    "larger-decimal": "0.5",
    "boiling-point": "0",  # wrong
    "blue-sky": "Because it is.",  # wrong
    "hexagon": "5",  # wrong
    "prime": "no",  # wrong
}


class ScriptedLlama:
    """Answers by matching the task prompt; everything else gets a canned reply."""

    delay = 0.0

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    def create_chat_completion(self, **kwargs: Any) -> Iterator[dict[str, Any]]:
        prompt = kwargs["messages"][-1]["content"]
        system = kwargs["messages"][0]["content"]
        science = bundled_package("science")
        assert science is not None
        reply = "Hi!"
        for task in science.benchmark.tasks:
            if task.prompt == prompt:
                reply = SCIENCE_ANSWERS[task.id]
                break
        if "Skill: Science" in system and prompt == "who are you":
            reply = "science-skilled"
        if ScriptedLlama.delay:
            time.sleep(ScriptedLlama.delay)
        yield {"choices": [{"delta": {"content": reply}, "finish_reason": None}]}
        yield {"choices": [{"delta": {}, "finish_reason": "stop"}]}


@pytest.fixture
def client(app_paths: AppPaths, tmp_path: Path) -> Iterator[TestClient]:
    ScriptedLlama.delay = 0.0
    provider = LlamaCppProvider(llama_factory=ScriptedLlama)
    app = create_app(CoreSettings(), app_paths, token=TOKEN, provider=provider)
    with TestClient(app, base_url="http://127.0.0.1") as c:
        c.headers.update({"Authorization": f"Bearer {TOKEN}"})
        c.post("/api/profile", json={"name": "Nova"})
        c.put("/api/storage/root", json={"root_path": str(tmp_path / "MyAI")})
        yield c


def _install_model(client: TestClient, tmp_path: Path) -> None:
    path = tmp_path / "MyAI" / "Models" / "m.gguf"
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


def _wait_job(client: TestClient, job_id: str, timeout: float = 20.0) -> dict[str, Any]:
    state = client.app.state.core  # type: ignore[attr-defined]
    state.jobs.wait(job_id, timeout)
    return client.get(f"/api/jobs/{job_id}").json()


# --- evaluation runner ----------------------------------------------------------------------


def test_evaluate_package_scores_areas_and_obeys_cancel() -> None:
    package = bundled_package("science")
    assert package is not None
    provider = LlamaCppProvider(llama_factory=ScriptedLlama)
    provider.load(Path(__file__), LoadConfig(model_id="m"))
    outcome = evaluate_package(package, provider.generate)
    assert outcome.score == pytest.approx(8.5 / 12, abs=1e-4)
    assert outcome.area_scores["arithmetic"] == 1.0
    assert len(outcome.tasks) == 12 and sum(t.passed for t in outcome.tasks) == 8

    control = JobControl()
    control.cancel.set()
    with pytest.raises(JobCancelledError):
        evaluate_package(package, provider.generate, control=control)


# --- job manager ----------------------------------------------------------------------------


def test_job_manager_pause_resume_cancel(session) -> None:  # type: ignore[no-untyped-def]
    from myai_core.db.models import AIProfile
    from myai_core.profile.identity import new_ai_id

    profile = AIProfile(ai_id=new_ai_id(), name="N")
    session.add(profile)
    session.commit()
    from sqlalchemy.orm import sessionmaker

    manager = JobManager(sessionmaker(bind=session.get_bind(), expire_on_commit=False))
    job = manager.create(
        session,
        kind="learn",
        ai_id=profile.ai_id,
        skill_id="science",
        model_id="m",
        compute_preset="balanced",
        total=5,
    )
    session.commit()
    with pytest.raises(JobBusyError):
        manager.create(
            session,
            kind="learn",
            ai_id=profile.ai_id,
            skill_id="x",
            model_id=None,
            compute_preset=None,
            total=1,
        )
    seen = threading.Event()

    def work(control: JobControl, progress: Any) -> dict[str, object]:
        for i in range(5):
            control.checkpoint()
            seen.set()
            progress(i + 1, 5)
            time.sleep(0.05)
        return {"ok": True}

    manager.start(job.id, work)
    assert seen.wait(2)
    assert manager.pause(job.id) is True
    time.sleep(0.2)
    session.expire_all()
    assert session.get(type(job), job.id).status == "paused"
    assert manager.resume(job.id) is True
    assert manager.cancel(job.id) is True
    manager.wait(job.id, 5)
    session.expire_all()
    done = session.get(type(job), job.id)
    assert done.status in {"cancelled", "completed"}
    assert manager.current_id() is None
    assert manager.pause(job.id) is False  # finished jobs cannot be controlled


# --- API flow -------------------------------------------------------------------------------


def test_learn_flow_end_to_end(client: TestClient, tmp_path: Path) -> None:
    # Before a model exists the preview says so and learning is refused.
    preview = client.get("/api/skills/science/learn-preview").json()
    assert preview["learnable"] is False and any("model" in b for b in preview["blockers"])
    assert client.post("/api/skills/science/learn").status_code == 409
    # Creative skills have no package and say so.
    video = client.get("/api/skills/video/learn-preview").json()
    assert video["package"] is None and "no measurable benchmark" in video["blockers"][0]
    # Locked by the tree.
    science_locked = client.get("/api/skills/science").json()
    assert science_locked["locked"] and "Research" in science_locked["locked_reason"]

    _install_model(client, tmp_path)
    preview = client.get("/api/skills/science/learn-preview").json()
    assert preview["learnable"] is False  # still locked: requires research
    assert preview["package"]["task_count"] == 12
    assert preview["recommended_compute"] in {"low", "balanced", "high"}

    # Learn the prerequisite chain: research needs conversation.
    for skill in ("conversation", "research"):
        job = client.post(f"/api/skills/{skill}/learn").json()
        assert job["kind"] == "learn" and job["status"] in {"queued", "running"}
        job = _wait_job(client, job["id"])
        assert job["status"] == "completed", job
    summary = client.get("/api/skills").json()
    by_id = {s["id"]: s for s in summary["skills"]}
    assert by_id["research"]["learned"] and by_id["research"]["level"] >= 1
    assert by_id["science"]["locked"] is False

    # Now science: the scripted model scores 8.5/12 -> level 71.
    job = client.post("/api/skills/science/learn").json()
    assert client.get("/api/status").json()["job"]["skill_id"] == "science"
    job = _wait_job(client, job["id"])
    assert job["status"] == "completed"
    assert job["result"]["level_after"] == 71 and job["result"]["level_before"] == 0
    science = client.get("/api/skills/science").json()
    assert science["learned"] and science["level"] == 71 and science["band"] == "expert"
    assert science["area_scores"]["arithmetic"] == 1.0 and science["package_version"] == "1.0.0"
    assert (tmp_path / "MyAI" / "Skills" / "science" / "1.0.0" / "benchmark.json").is_file()

    history = client.get("/api/skills/science/evaluations").json()
    assert len(history) == 1 and history[0]["level_after"] == 71
    assert len(history[0]["task_results"]) == 12
    assert any(e["action"] == "skill_learned" for e in client.get("/api/audit").json())

    # Already learned: refused; evaluate re-runs and records history.
    assert client.post("/api/skills/science/learn").status_code == 409
    job = client.post("/api/skills/science/evaluate").json()
    job = _wait_job(client, job["id"])
    assert job["status"] == "completed"
    assert len(client.get("/api/skills/history").json()) == 4
    assert any(e["action"] == "skill_evaluated" for e in client.get("/api/audit").json())

    # Degrees and achievements derive from measured levels only.
    summary = client.get("/api/skills").json()
    degrees = {d["id"]: d for d in summary["degrees"]}
    assert degrees["research"]["earned"] is True
    assert degrees["research"]["level"] == min(by_id["research"]["level"], 71)
    assert degrees["media"]["earned"] is False and "cannot be learned" in degrees["media"]["note"]
    achievements = {a["id"]: a for a in summary["achievements"]}
    assert achievements["first_lesson"]["earned"] is True
    assert achievements["coding_specialist"]["earned"] is False

    # Learned skills' instructions reach the chat prompt.
    conv = client.post("/api/chat/conversations", json={}).json()
    r = client.post(
        f"/api/chat/conversations/{conv['id']}/messages", json={"content": "who are you"}
    )
    assert "science-skilled" in r.text

    # Console commands.
    res = client.post("/api/commands", json={"text": "/history"}).json()
    assert res["outcome"] == "ok" and "Science" in res["message"]
    # /train previews and starts nothing until it is confirmed (Phase 4).
    res = client.post("/api/commands", json={"text": "/train science level 80"}).json()
    assert res["outcome"] == "ok" and "Current level: 71" in res["message"]
    assert "Target level: 80" in res["message"]
    assert "weights are not changed" in res["message"]
    assert res["suggestions"][0] == "/train science start"
    assert "job" not in res["data"]
    assert client.get("/api/jobs/current").json() is None
    res = client.post("/api/commands", json={"text": "/learn coding"}).json()
    assert res["outcome"] == "ok" and "Start learning?" in res["message"]
    assert res["suggestions"][0] == "/learn coding start"


def test_console_learn_start_and_stop(client: TestClient, tmp_path: Path) -> None:
    _install_model(client, tmp_path)
    ScriptedLlama.delay = 0.3
    res = client.post("/api/commands", json={"text": "/learn conversation start"}).json()
    assert res["outcome"] == "ok" and res["data"]["job"]["kind"] == "learn"
    job_id = res["data"]["job"]["id"]
    status = client.post("/api/commands", json={"text": "/status"}).json()
    assert "Learning Conversation" in status["message"]
    assert client.post("/api/commands", json={"text": "/pause"}).json()["outcome"] == "ok"
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "paused"
    assert client.post("/api/commands", json={"text": "/resume"}).json()["outcome"] == "ok"
    assert client.post("/api/commands", json={"text": "/stop"}).json()["outcome"] == "ok"
    job = _wait_job(client, job_id)
    assert job["status"] == "cancelled"
    # Cancelled learning leaves the skill unlearned: nothing is faked.
    assert client.get("/api/skills/conversation").json()["learned"] is False
    assert client.get("/api/jobs/current").json() is None
    assert client.post("/api/commands", json={"text": "/stop"}).json()["outcome"] == "unavailable"


def test_jobs_endpoints(client: TestClient, tmp_path: Path) -> None:
    assert client.get("/api/jobs").json() == []
    assert client.get("/api/jobs/nope").status_code == 404
    _install_model(client, tmp_path)
    # The one-at-a-time rule is about a job that is actually running, so the first job is
    # slowed enough to still be in flight when the second request arrives. Without this the
    # scripted model can finish all 12 tasks before the next line runs, and the assertion
    # becomes a race that fails on whichever machine is quickest.
    ScriptedLlama.delay = 0.05
    job = client.post("/api/skills/conversation/learn").json()
    assert client.post("/api/skills/writing/learn").status_code == 409  # one at a time
    _wait_job(client, job["id"])
    assert client.get("/api/jobs").json()[0]["id"] == job["id"]
    assert client.post(f"/api/jobs/{job['id']}/pause").status_code == 409
