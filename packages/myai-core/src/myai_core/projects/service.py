"""Projects, and the one decision that makes them safe to delete.

A project groups conversations, memories and documents. It is a *label*, not a container:
each row carries a nullable `project_id`, and everything works perfectly well carrying none.

**The delete question.** "Delete this project" is ambiguous in a way that matters. Someone
tidying up means "get rid of the label"; someone abandoning a piece of work might mean "and
everything I wrote for it". Those differ by a year of conversation, and a default would
silently pick one on behalf of people who meant the other. So `delete` takes a disposition
with no default: the caller has to say `KEEP` or `DELETE_CONTENTS`, and the API surfaces it
as a required field. The database backs this up with `ON DELETE SET NULL`, so even a bug
here unfiles rather than destroys.

Archiving exists because it is what most people actually want when they reach for delete: it
takes a project out of the way and is reversible.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TypeVar

from sqlalchemy import delete as sql_delete
from sqlalchemy import func, select, update
from sqlalchemy.orm import InstrumentedAttribute, Session
from ulid import ULID

from myai_core.db.models import Conversation, Document, Memory, Message, Project

# The three kinds of row that can be filed under a project. A constrained TypeVar rather
# than a union, so each substitution is type-checked against its own model.
Member = TypeVar("Member", Conversation, Memory, Document)

MAX_NAME = 200


class ContentsDisposition(StrEnum):
    """What happens to a project's contents when the project is deleted."""

    KEEP = "keep"
    """Unfile them. They stop belonging to a project and stay exactly where they are."""

    DELETE_CONTENTS = "delete"
    """Delete the conversations, memories and documents too. Not reversible."""


@dataclass(frozen=True, slots=True)
class ProjectContents:
    """How much is filed under a project, for a confirmation that states the cost."""

    conversations: int
    memories: int
    documents: int

    @property
    def total(self) -> int:
        return self.conversations + self.memories + self.documents


class ProjectNotFoundError(LookupError):
    """No project with that id belongs to this AI."""


class ProjectService:
    def __init__(self, session: Session, ai_id: str) -> None:
        self.session = session
        self.ai_id = ai_id

    # --- the project itself ---------------------------------------------------------------

    def create(self, name: str, description: str = "") -> Project:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("A project needs a name.")
        project = Project(
            id=f"prj_{ULID()}",
            ai_id=self.ai_id,
            name=cleaned[:MAX_NAME],
            description=description.strip(),
        )
        self.session.add(project)
        self.session.flush()
        return project

    def list(self, *, include_archived: bool = False) -> list[Project]:
        query = select(Project).where(Project.ai_id == self.ai_id)
        if not include_archived:
            query = query.where(Project.archived_at.is_(None))
        return list(self.session.scalars(query.order_by(Project.updated_at.desc())).all())

    def get(self, project_id: str) -> Project:
        project = self.session.scalar(
            select(Project).where(Project.id == project_id, Project.ai_id == self.ai_id)
        )
        if project is None:
            raise ProjectNotFoundError(project_id)
        return project

    def update(
        self, project_id: str, *, name: str | None = None, description: str | None = None
    ) -> Project:
        project = self.get(project_id)
        if name is not None:
            cleaned = name.strip()
            if not cleaned:
                raise ValueError("A project needs a name.")
            project.name = cleaned[:MAX_NAME]
        if description is not None:
            project.description = description.strip()
        project.version += 1
        self.session.flush()
        return project

    def archive(self, project_id: str, *, archived: bool = True) -> Project:
        """Put a project away, or bring it back. Contents are untouched either way."""
        project = self.get(project_id)
        project.archived_at = datetime.now(tz=UTC) if archived else None
        project.version += 1
        self.session.flush()
        return project

    def contents(self, project_id: str) -> ProjectContents:
        """What is filed under this project. Read before deleting, so the warning is true."""
        self.get(project_id)
        return ProjectContents(
            conversations=self._count(Conversation, project_id),
            memories=self._count(Memory, project_id),
            documents=self._count(Document, project_id),
        )

    def delete(self, project_id: str, disposition: ContentsDisposition) -> ProjectContents:
        """Delete a project, having been told what to do with what is in it.

        There is no default disposition anywhere in this path — not here, not in the schema,
        not in the CLI. Returns what was in it, so the caller can report what happened.
        """
        project = self.get(project_id)
        held = self.contents(project_id)

        if disposition is ContentsDisposition.DELETE_CONTENTS:
            conversation_ids = list(
                self.session.scalars(
                    select(Conversation.id).where(Conversation.project_id == project_id)
                ).all()
            )
            if conversation_ids:
                # Messages first: they point at the conversations about to go.
                self.session.execute(
                    sql_delete(Message).where(Message.conversation_id.in_(conversation_ids))
                )
            for model in (Conversation, Memory, Document):
                self.session.execute(sql_delete(model).where(model.project_id == project_id))
        else:
            for model in (Conversation, Memory, Document):
                self.session.execute(
                    update(model).where(model.project_id == project_id).values(project_id=None)
                )

        self.session.delete(project)
        self.session.flush()
        return held

    # --- membership -----------------------------------------------------------------------

    def file_conversation(self, conversation_id: str, project_id: str | None) -> None:
        self._file(Conversation, Conversation.id, conversation_id, project_id)

    def file_memory(self, memory_uid: str, project_id: str | None) -> None:
        self._file(Memory, Memory.uid, memory_uid, project_id)

    def file_document(self, document_id: str, project_id: str | None) -> None:
        self._file(Document, Document.id, document_id, project_id)

    def _file(
        self,
        model: type[Member],
        key_column: InstrumentedAttribute[str],
        key: str,
        project_id: str | None,
    ) -> None:
        """Move one row into a project, or out of every project when `project_id` is None."""
        if project_id is not None:
            self.get(project_id)  # refuse to file into someone else's project, or a missing one
        row = self.session.scalar(select(model).where(key_column == key, model.ai_id == self.ai_id))
        if row is None:
            raise LookupError(key)
        row.project_id = project_id
        self.session.flush()

    def _count(self, model: type[Member], project_id: str) -> int:
        counted = self.session.execute(
            select(func.count()).select_from(model).where(model.project_id == project_id)
        ).scalar_one()
        return int(counted)
