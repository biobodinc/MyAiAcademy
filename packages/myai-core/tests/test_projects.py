"""Projects, and above all what deleting one does.

The delete question is the reason this feature needs careful tests rather than a smoke test.
"Delete this project" can reasonably mean "get rid of the label" or "get rid of the work",
and the difference is unrecoverable in one direction, so every path through it is pinned
here: both dispositions, the refusal to guess, and the database's own backstop.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from myai_core.db.models import Conversation, Document, Memory, Message, Project
from myai_core.projects.service import (
    ContentsDisposition,
    ProjectNotFoundError,
    ProjectService,
)

AI_ID = "ai_test"


@pytest.fixture
def service(session):
    from myai_core.db.models import AIProfile

    session.add(AIProfile(ai_id=AI_ID, name="Nova"))
    session.flush()
    return ProjectService(session, AI_ID)


def _fill(session, project_id: str | None) -> None:
    """One conversation with a message, one memory, one document, all filed together."""
    session.add(Conversation(id="c1", ai_id=AI_ID, title="Notes", project_id=project_id))
    session.flush()
    session.add(Message(uid="m1", conversation_id="c1", role="user", content="hello"))
    session.add(Memory(uid="mem1", ai_id=AI_ID, content="remember this", project_id=project_id))
    session.add(
        Document(
            id="d1",
            ai_id=AI_ID,
            title="Spec",
            media_type="text/plain",
            size_bytes=10,
            sha256="x" * 64,
            project_id=project_id,
        )
    )
    session.flush()


# --- the basics ----------------------------------------------------------------------------


def test_a_project_starts_empty_and_unarchived(service):
    project = service.create("Kitchen rebuild", "Everything about the kitchen")

    assert project.name == "Kitchen rebuild"
    assert project.archived_at is None
    assert service.contents(project.id).total == 0


def test_a_project_needs_a_name(service):
    with pytest.raises(ValueError):
        service.create("   ")


def test_listing_hides_archived_projects_unless_asked(service):
    kept = service.create("Live")
    archived = service.create("Old")
    service.archive(archived.id)

    assert [p.id for p in service.list()] == [kept.id]
    assert {p.id for p in service.list(include_archived=True)} == {kept.id, archived.id}


def test_archiving_is_reversible_and_touches_nothing_inside(service, session):
    project = service.create("Work")
    _fill(session, project.id)

    service.archive(project.id)
    assert service.contents(project.id).total == 3

    service.archive(project.id, archived=False)
    assert service.get(project.id).archived_at is None
    assert service.contents(project.id).total == 3


def test_another_ai_s_project_is_not_reachable(service, session):
    project = service.create("Mine")
    stranger = ProjectService(session, "ai_someone_else")

    with pytest.raises(ProjectNotFoundError):
        stranger.get(project.id)


# --- the delete question --------------------------------------------------------------------


def test_deleting_with_keep_unfiles_the_contents_and_destroys_nothing(service, session):
    project = service.create("Kitchen rebuild")
    _fill(session, project.id)

    held = service.delete(project.id, ContentsDisposition.KEEP)

    assert held.conversations == 1 and held.memories == 1 and held.documents == 1
    assert session.get(Project, project.id) is None
    # Everything survives, now belonging to no project.
    assert session.get(Conversation, "c1").project_id is None
    assert session.scalar(select(Memory)).project_id is None
    assert session.get(Document, "d1").project_id is None
    assert session.scalar(select(Message)) is not None


def test_deleting_with_delete_contents_removes_the_work_too(service, session):
    project = service.create("Abandoned")
    _fill(session, project.id)

    held = service.delete(project.id, ContentsDisposition.DELETE_CONTENTS)

    assert held.total == 3
    assert session.get(Project, project.id) is None
    assert session.get(Conversation, "c1") is None
    assert session.get(Document, "d1") is None
    assert session.scalar(select(Memory)) is None
    # Messages go with their conversation rather than being orphaned.
    assert session.scalar(select(Message)) is None


def test_deleting_a_project_leaves_other_projects_alone(service, session):
    doomed = service.create("Doomed")
    safe = service.create("Safe")
    session.add(Conversation(id="c-safe", ai_id=AI_ID, title="Keep", project_id=safe.id))
    _fill(session, doomed.id)

    service.delete(doomed.id, ContentsDisposition.DELETE_CONTENTS)

    assert session.get(Conversation, "c-safe") is not None
    assert service.contents(safe.id).conversations == 1


def test_deleting_reports_what_was_in_it(service, session):
    project = service.create("Counted")
    _fill(session, project.id)

    held = service.delete(project.id, ContentsDisposition.KEEP)

    assert (held.conversations, held.memories, held.documents, held.total) == (1, 1, 1, 3)


def test_unfiled_work_is_untouched_by_any_delete(service, session):
    project = service.create("Something")
    _fill(session, None)  # filed nowhere

    service.delete(project.id, ContentsDisposition.DELETE_CONTENTS)

    assert session.get(Conversation, "c1") is not None
    assert session.get(Document, "d1") is not None


# --- membership -----------------------------------------------------------------------------


def test_filing_and_unfiling_a_conversation(service, session):
    project = service.create("Filing")
    session.add(Conversation(id="c1", ai_id=AI_ID, title="Notes"))
    session.flush()

    service.file_conversation("c1", project.id)
    assert service.contents(project.id).conversations == 1

    service.file_conversation("c1", None)
    assert service.contents(project.id).conversations == 0
    assert session.get(Conversation, "c1") is not None


def test_filing_into_a_project_that_does_not_exist_is_refused(service, session):
    session.add(Conversation(id="c1", ai_id=AI_ID, title="Notes"))
    session.flush()

    with pytest.raises(ProjectNotFoundError):
        service.file_conversation("c1", "prj_nope")


def test_filing_something_that_does_not_exist_is_refused(service):
    project = service.create("Filing")
    with pytest.raises(LookupError):
        service.file_conversation("no-such-conversation", project.id)


# --- through the API -------------------------------------------------------------------------


@pytest.fixture
def api(client: TestClient) -> TestClient:
    client.post("/api/profile", json={"name": "Nova", "owner_name": "Alex"})
    return client


def test_the_api_round_trips_a_project(api):
    created = api.post("/api/projects", json={"name": "Kitchen", "description": "rebuild"})
    assert created.status_code == 201
    project_id = created.json()["id"]

    assert api.get("/api/projects").json()[0]["name"] == "Kitchen"
    renamed = api.patch(f"/api/projects/{project_id}", json={"name": "Kitchen rebuild"})
    assert renamed.json()["name"] == "Kitchen rebuild"


def test_the_api_will_not_delete_without_being_told_what_to_do_with_the_contents(api):
    """No default, so a caller that forgets gets a 422 rather than a guess."""
    project_id = api.post("/api/projects", json={"name": "Kitchen"}).json()["id"]

    assert api.post(f"/api/projects/{project_id}/delete", json={}).status_code == 422


def test_the_api_rejects_a_disposition_it_does_not_know(api):
    project_id = api.post("/api/projects", json={"name": "Kitchen"}).json()["id"]

    response = api.post(f"/api/projects/{project_id}/delete", json={"contents": "maybe"})

    assert response.status_code == 422


def test_the_api_reports_contents_before_a_delete_is_confirmed(api):
    project_id = api.post("/api/projects", json={"name": "Kitchen"}).json()["id"]
    conversation = api.post("/api/chat/conversations", json={"title": "Notes"})
    assert conversation.status_code in (200, 201)
    api.put(
        f"/api/projects/items/conversations/{conversation.json()['id']}",
        json={"project_id": project_id},
    )

    contents = api.get(f"/api/projects/{project_id}/contents").json()

    assert contents["conversations"] == 1
    assert contents["total"] == 1


def test_the_api_keeps_contents_when_asked_to(api):
    project_id = api.post("/api/projects", json={"name": "Kitchen"}).json()["id"]
    conversation_id = api.post("/api/chat/conversations", json={"title": "Notes"}).json()["id"]
    api.put(f"/api/projects/items/conversations/{conversation_id}", json={"project_id": project_id})

    deleted = api.post(f"/api/projects/{project_id}/delete", json={"contents": "keep"})

    assert deleted.status_code == 200
    assert deleted.json()["conversations"] == 1
    surviving = [c["id"] for c in api.get("/api/chat/conversations").json()]
    assert conversation_id in surviving


def test_the_api_deletes_contents_when_asked_to(api):
    project_id = api.post("/api/projects", json={"name": "Kitchen"}).json()["id"]
    conversation_id = api.post("/api/chat/conversations", json={"title": "Notes"}).json()["id"]
    api.put(f"/api/projects/items/conversations/{conversation_id}", json={"project_id": project_id})

    deleted = api.post(f"/api/projects/{project_id}/delete", json={"contents": "delete"})

    assert deleted.status_code == 200
    surviving = [c["id"] for c in api.get("/api/chat/conversations").json()]
    assert conversation_id not in surviving


def test_a_missing_project_is_a_404(api):
    assert api.get("/api/projects/prj_nope").status_code == 404
    assert api.get("/api/projects/prj_nope/contents").status_code == 404
    assert api.post("/api/projects/prj_nope/delete", json={"contents": "keep"}).status_code == 404


# --- what the migration must not have broken -------------------------------------------------


def test_memory_search_still_works_after_the_projects_migration(session):
    """SQLite rebuilds a table to add a foreign key, dropping its triggers with it.

    `memories` carries an external-content FTS5 index kept current by triggers, and losing
    them breaks search with no error anywhere — writes succeed, queries just quietly return
    nothing. Migration 0011 recreates them; this fails if a later migration forgets to.
    """
    from myai_core.db.models import AIProfile
    from myai_core.memory.service import MemoryCreate, MemoryService

    session.add(AIProfile(ai_id=AI_ID, name="Nova"))
    session.flush()
    service = MemoryService(session, AI_ID)
    service.add(MemoryCreate(content="The horse project is a cinematic adventure film"))

    assert [m.content for m in service.search("horses")] == [
        "The horse project is a cinematic adventure film"
    ]
