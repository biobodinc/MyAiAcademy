"""What travels between a user's own devices, and what deliberately does not (spec §16, §72).

This file is the whole answer to "will my AI be the same on my laptop?", and it is written
as a list rather than a rule because the interesting part is the exclusions. Three kinds of
row are kept off the wire on purpose:

* **Credentials and security records.** Devices, pairing codes and the audit log stay where
  they were written. A device's credential is its own; copying it to another machine would
  make revocation meaningless, and an audit log that arrived from elsewhere is not evidence
  of anything. Each installation keeps its own account of who did what to it.
* **Facts about one machine.** Storage roots, installed models, downloads, hardware
  benchmarks, compute limits. A laptop's model directory is not a desktop's, and a
  benchmark measured on one machine is a lie about the other.
* **Work in progress.** Jobs belong to the machine running them. A training run cannot be
  continued somewhere else, and a job row that says "running" on a computer that is asleep
  would be a dashboard that lies.

Knowledge documents are excluded for a different reason: the file bytes have nowhere to go
yet. Syncing the metadata alone would put a document in the list on the other device that
could not be opened or searched, which is worse than not showing it. That waits for file
transfer, and `test_sync.py` holds this file to naming a reason for every table.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from myai_core.db import models


@dataclass(frozen=True, slots=True)
class SyncedEntity:
    """One kind of row that travels, and how to recognise the same row on two machines."""

    name: str
    model: type[models.SyncedBase]
    uid_attr: str
    """The column that means the same thing on every device. Never the primary key: an
    autoincrementing integer is a fact about one database's insert order."""
    fields: tuple[str, ...]
    """The columns that travel. Anything not listed is local and stays local."""
    parents: tuple[str, ...] = field(default=())
    """Entities that must be applied first, so a message never arrives before its
    conversation."""
    rebind_ai: bool = False
    """True when a column names the AI profile, which has a different primary key on every
    installation. See ``engine._rebind``: the row is attached to the receiving machine's own
    AI rather than carrying a key that means nothing there."""


PROJECT = SyncedEntity(
    name="project",
    model=models.Project,
    uid_attr="id",
    fields=(
        "id",
        "ai_id",
        "name",
        "description",
        "created_at",
        "updated_at",
        "version",
        "archived_at",
    ),
    rebind_ai=True,
)

CONVERSATION = SyncedEntity(
    name="conversation",
    model=models.Conversation,
    uid_attr="id",
    fields=("id", "ai_id", "title", "created_at", "updated_at", "version", "project_id"),
    parents=("project",),
    rebind_ai=True,
)

MESSAGE = SyncedEntity(
    name="message",
    model=models.Message,
    uid_attr="uid",
    fields=(
        "uid",
        "conversation_id",
        "role",
        "content",
        "created_at",
        "model_id",
        "finish_reason",
    ),
    parents=("conversation",),
)

MEMORY = SyncedEntity(
    name="memory",
    model=models.Memory,
    uid_attr="uid",
    fields=(
        "uid",
        "ai_id",
        "content",
        "category",
        "created_at",
        "updated_at",
        "version",
        "project_id",
    ),
    parents=("project",),
    rebind_ai=True,
)

SKILL_STATE = SyncedEntity(
    name="skill_state",
    model=models.SkillState,
    uid_attr="skill_id",
    fields=(
        "ai_id",
        "skill_id",
        "status",
        "level",
        "last_evaluation_score",
        "learned_at",
        "updated_at",
        "version",
        "package_version",
        "trained_at",
    ),
    rebind_ai=True,
)

SYNCED: tuple[SyncedEntity, ...] = (PROJECT, CONVERSATION, MESSAGE, MEMORY, SKILL_STATE)
"""In apply order: a parent is always earlier in this tuple than anything referencing it."""

BY_NAME: dict[str, SyncedEntity] = {entity.name: entity for entity in SYNCED}
BY_MODEL: dict[type[models.SyncedBase], SyncedEntity] = {e.model: e for e in SYNCED}


NOT_SYNCED: dict[str, str] = {
    "devices": "A credential belongs to the machine it was issued to; copying it would make "
    "revoking it meaningless.",
    "pairing_codes": "Single-use and short-lived. A code is only meaningful to the host that "
    "issued it.",
    "audit_events": "Each installation keeps its own account of what was done to it. An audit "
    "log that arrived from elsewhere is not evidence.",
    "account_info": "Which account this installation was paired to. Each device is added to "
    "an account deliberately, by someone entering a code on that device; copying the link "
    "would enrol a machine nobody paired, and revoking one device would not reach it.",
    "sync_identity": "This installation's own name and clock.",
    "sync_peers": "Who this installation syncs with, and how far it has got.",
    "sync_tombstones": "Deletions travel as changes, not as rows of their own.",
    "sync_conflicts": "A local record of what was overwritten here, for the person at this "
    "machine to look at.",
    "preferences": "Settings belong to the machine: window state, compute limits, a chosen "
    "model directory.",
    "storage_config": "A storage root is a path on one computer.",
    "jobs": "A job belongs to the machine running it, and cannot be continued elsewhere.",
    "installed_models": "Model files live on one disk. The catalog is the same everywhere; "
    "which files are present is not.",
    "model_downloads": "In progress on one machine.",
    "model_license_acceptances": "Recorded against the installation that accepted.",
    "hardware_benchmarks": "A measurement of one machine. Copying it would be a lie about "
    "the other.",
    "ai_profile": "The AI's identity row is local: its primary key is generated per "
    "installation and means nothing on another machine. What the AI knows and has learned "
    "travels and is re-bound to the receiving machine's own AI (engine._rebind). Making two "
    "installations agree on one identity — the same name and goals everywhere — is a "
    "separate question that needs the account decision first.",
    "documents": "The file itself has nowhere to go yet. A document in the list that cannot "
    "be opened or searched is worse than not showing it.",
    "chunks": "Derived from a document, and rebuilt wherever the file actually is.",
    "skill_evaluations": "The history of runs on this machine. Levels travel; the transcript "
    "of how they were reached does not.",
    "training_runs": "As above: the outcome travels with the skill, the round-by-round "
    "record stays where it was produced.",
}
"""Every table that is not synced, with the reason. Tested for completeness, so a new table
cannot be added without someone deciding which side of this line it falls on."""
