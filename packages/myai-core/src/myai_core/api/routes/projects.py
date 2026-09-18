"""Projects: grouping conversations, memories and documents.

The delete route is the one worth reading. `contents` has no default and no "are you sure"
boolean — the caller states what should happen to what is filed under the project, because
the two answers differ by a year of someone's work. `GET /projects/{id}/contents` exists so a
confirmation can say the actual numbers rather than a vague warning.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import Field

from myai_core.api.deps import AuditDep, ProfileDep, SessionDep
from myai_core.audit.service import AuditCategory
from myai_core.db.models import Project
from myai_core.projects.service import (
    ContentsDisposition,
    ProjectNotFoundError,
    ProjectService,
)
from myai_core.schemas import ApiModel

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectRead(ApiModel):
    id: str
    name: str
    description: str
    created_at: datetime
    updated_at: datetime
    archived: bool


class ProjectContentsRead(ApiModel):
    conversations: int
    memories: int
    documents: int
    total: int


class ProjectCreate(ApiModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)


class ProjectUpdate(ApiModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class ArchiveRequest(ApiModel):
    archived: bool


class DeleteRequest(ApiModel):
    contents: ContentsDisposition = Field(
        description=(
            "What happens to the conversations, memories and documents filed under this "
            "project. 'keep' unfiles them and leaves them alone; 'delete' removes them too "
            "and cannot be undone. There is no default: a wrong guess here is unrecoverable."
        )
    )


class FileRequest(ApiModel):
    project_id: str | None = Field(
        default=None, description="Null takes the item out of every project."
    )


def _read(project: Project) -> ProjectRead:
    return ProjectRead(
        id=project.id,
        name=project.name,
        description=project.description,
        created_at=project.created_at,
        updated_at=project.updated_at,
        archived=project.archived_at is not None,
    )


def _svc(session: SessionDep, profile: ProfileDep) -> ProjectService:
    row = profile.get()
    if row is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Create your AI profile first.")
    return ProjectService(session, row.ai_id)


@router.get("", response_model=list[ProjectRead])
def list_projects(
    session: SessionDep, profile: ProfileDep, include_archived: bool = False
) -> list[ProjectRead]:
    return [_read(p) for p in _svc(session, profile).list(include_archived=include_archived)]


@router.post("", response_model=ProjectRead, status_code=201)
def create_project(
    body: ProjectCreate, session: SessionDep, profile: ProfileDep, audit: AuditDep
) -> ProjectRead:
    project = _svc(session, profile).create(body.name, body.description)
    audit.record(
        AuditCategory.PROFILE,
        "project_created",
        f"Project {project.name} was created",
        {"project_id": project.id},
    )
    return _read(project)


@router.get("/{project_id}", response_model=ProjectRead)
def read_project(project_id: str, session: SessionDep, profile: ProfileDep) -> ProjectRead:
    try:
        return _read(_svc(session, profile).get(project_id))
    except ProjectNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such project.") from exc


@router.get("/{project_id}/contents", response_model=ProjectContentsRead)
def read_contents(project_id: str, session: SessionDep, profile: ProfileDep) -> ProjectContentsRead:
    """How much is filed here — so a confirmation can state the cost rather than imply it."""
    try:
        held = _svc(session, profile).contents(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such project.") from exc
    return ProjectContentsRead(
        conversations=held.conversations,
        memories=held.memories,
        documents=held.documents,
        total=held.total,
    )


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: str, body: ProjectUpdate, session: SessionDep, profile: ProfileDep
) -> ProjectRead:
    try:
        return _read(
            _svc(session, profile).update(project_id, name=body.name, description=body.description)
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such project.") from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("/{project_id}/archive", response_model=ProjectRead)
def archive_project(
    project_id: str, body: ArchiveRequest, session: SessionDep, profile: ProfileDep
) -> ProjectRead:
    """Put a project away, or bring it back. Nothing filed under it is touched."""
    try:
        return _read(_svc(session, profile).archive(project_id, archived=body.archived))
    except ProjectNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such project.") from exc


@router.post("/{project_id}/delete", response_model=ProjectContentsRead)
def delete_project(
    project_id: str,
    body: DeleteRequest,
    session: SessionDep,
    profile: ProfileDep,
    audit: AuditDep,
) -> ProjectContentsRead:
    """Delete a project. `contents` is required — see `DeleteRequest`.

    POST rather than DELETE because this carries a body that must not be optional, and a
    DELETE with a required body is a request some proxies and clients quietly strip.
    """
    service = _svc(session, profile)
    try:
        project = service.get(project_id)
        name = project.name
        held = service.delete(project_id, body.contents)
    except ProjectNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such project.") from exc

    audit.record(
        AuditCategory.PROFILE,
        "project_deleted",
        (
            f"Project {name} was deleted and its {held.total} item(s) deleted with it"
            if body.contents is ContentsDisposition.DELETE_CONTENTS
            else f"Project {name} was deleted; its {held.total} item(s) were kept"
        ),
        {"project_id": project_id, "contents": body.contents.value, "items": held.total},
    )
    return ProjectContentsRead(
        conversations=held.conversations,
        memories=held.memories,
        documents=held.documents,
        total=held.total,
    )


@router.put("/items/conversations/{conversation_id}", status_code=204)
def file_conversation(
    conversation_id: str, body: FileRequest, session: SessionDep, profile: ProfileDep
) -> None:
    _file(lambda s: s.file_conversation(conversation_id, body.project_id), session, profile)


@router.put("/items/memories/{memory_uid}", status_code=204)
def file_memory(
    memory_uid: str, body: FileRequest, session: SessionDep, profile: ProfileDep
) -> None:
    _file(lambda s: s.file_memory(memory_uid, body.project_id), session, profile)


@router.put("/items/documents/{document_id}", status_code=204)
def file_document(
    document_id: str, body: FileRequest, session: SessionDep, profile: ProfileDep
) -> None:
    _file(lambda s: s.file_document(document_id, body.project_id), session, profile)


def _file(work: Callable[[ProjectService], None], session: SessionDep, profile: ProfileDep) -> None:
    try:
        work(_svc(session, profile))
    except ProjectNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such project.") from exc
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such item.") from exc
