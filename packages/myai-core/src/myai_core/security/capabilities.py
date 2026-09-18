"""What a paired program is allowed to do, stated as a list (spec §47, §53, §75).

Until now a paired client could do anything the owner could, minus a handful of owner-only
actions. That is fine for the user's own CLI and wrong for a third-party tool: "let this
thing use my AI" should not also mean "let it read every conversation I have ever had".

So access is a **set of named capabilities**, and the important half of the design is the
default. A route this file has not classified is refused to a scoped client rather than
allowed, and a test fails if any router reaches the application without a capability
declared. The failure mode of "someone added an endpoint and forgot" is therefore a red
test, not a quietly over-broad grant — which is the same reasoning as the sync registry and
the erase coverage check, for the same reason: silent over-permission is invisible until it
matters.

Read and write are separate on purpose. A tool that summarises your notes needs to read
them; almost none of them need to rewrite them, and the difference is exactly what a person
wants to be asked about.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Capability(StrEnum):
    """One named thing a client may be allowed to do."""

    STATUS_READ = "status:read"
    HARDWARE_READ = "hardware:read"
    CHAT_READ = "chat:read"
    CHAT_WRITE = "chat:write"
    MEMORY_READ = "memory:read"
    MEMORY_WRITE = "memory:write"
    PROJECTS_READ = "projects:read"
    PROJECTS_WRITE = "projects:write"
    KNOWLEDGE_READ = "knowledge:read"
    KNOWLEDGE_WRITE = "knowledge:write"
    SKILLS_READ = "skills:read"
    SKILLS_TRAIN = "skills:train"
    MODELS_READ = "models:read"
    MODELS_MANAGE = "models:manage"
    SYNC = "sync"
    ACTIVITY_READ = "activity:read"


@dataclass(frozen=True, slots=True)
class CapabilityInfo:
    """What granting one actually means, in words the person deciding will understand."""

    capability: Capability
    title: str
    detail: str
    sensitive: bool = False
    """True where a grant exposes or changes the user's own content, rather than machine
    facts. These are the ones a consent screen should make someone look at twice."""


CAPABILITIES: tuple[CapabilityInfo, ...] = (
    CapabilityInfo(
        Capability.STATUS_READ,
        "See whether your AI is running",
        "Whether a model is loaded, whether a job is running, and the version. No content.",
    ),
    CapabilityInfo(
        Capability.HARDWARE_READ,
        "See this computer's specification",
        "Processor, memory and graphics card, and how busy they are. Nothing you have written.",
    ),
    CapabilityInfo(
        Capability.CHAT_READ,
        "Read your conversations",
        "Every message you have exchanged with your AI, including old ones.",
        sensitive=True,
    ),
    CapabilityInfo(
        Capability.CHAT_WRITE,
        "Talk to your AI",
        "Send messages and start conversations. Replies count against your compute, not ours.",
        sensitive=True,
    ),
    CapabilityInfo(
        Capability.MEMORY_READ,
        "Read what your AI remembers",
        "The facts you have explicitly told it to remember about you.",
        sensitive=True,
    ),
    CapabilityInfo(
        Capability.MEMORY_WRITE,
        "Change what your AI remembers",
        "Add, edit and delete remembered facts. A tool with this can rewrite what your AI "
        "believes about you.",
        sensitive=True,
    ),
    CapabilityInfo(
        Capability.PROJECTS_READ,
        "See how your work is grouped",
        "The names of your projects and how much is filed under each. Not the contents — "
        "reading those still needs the grant for conversations, memories or files.",
    ),
    CapabilityInfo(
        Capability.PROJECTS_WRITE,
        "Group and ungroup your work",
        "Create, rename and delete projects, and move things between them. Deleting a project "
        "can be asked to delete everything filed under it.",
        sensitive=True,
    ),
    CapabilityInfo(
        Capability.KNOWLEDGE_READ,
        "Read your knowledge files",
        "The documents you have added, and their contents.",
        sensitive=True,
    ),
    CapabilityInfo(
        Capability.KNOWLEDGE_WRITE,
        "Add and remove knowledge files",
        "Put documents into your AI's knowledge, and take them out again.",
        sensitive=True,
    ),
    CapabilityInfo(
        Capability.SKILLS_READ,
        "See what your AI has learned",
        "Skill levels, history and degrees. No conversation content.",
    ),
    CapabilityInfo(
        Capability.SKILLS_TRAIN,
        "Start learning and training",
        "Begin jobs that use this computer's processor and graphics card for a long time.",
    ),
    CapabilityInfo(
        Capability.MODELS_READ,
        "See which models are installed",
        "The catalog and what is downloaded. No model files are sent anywhere.",
    ),
    CapabilityInfo(
        Capability.MODELS_MANAGE,
        "Download and remove models",
        "Start downloads that use your connection and disk, and delete installed models.",
    ),
    CapabilityInfo(
        Capability.SYNC,
        "Sync with your other devices",
        "Exchange changes with your own installations. This is what a second device needs.",
        sensitive=True,
    ),
    CapabilityInfo(
        Capability.ACTIVITY_READ,
        "Read the activity log",
        "What has been done to this installation, and by which client.",
    ),
)

BY_NAME: dict[Capability, CapabilityInfo] = {info.capability: info for info in CAPABILITIES}

DEFAULT_GRANT: frozenset[Capability] = frozenset(
    {
        Capability.STATUS_READ,
        Capability.SKILLS_READ,
        Capability.MODELS_READ,
    }
)
"""What a client gets when the owner names nothing: enough to show a dashboard, and nothing
the user has written. Widening it is a deliberate act, which is the point."""

MOBILE_GRANT: frozenset[Capability] = DEFAULT_GRANT | {
    Capability.CHAT_READ,
    Capability.CHAT_WRITE,
    Capability.MEMORY_READ,
    Capability.PROJECTS_READ,
    Capability.SYNC,
}
"""A phone acting as a controller. It can see how work is grouped, but not regroup it —
and still not knowledge files, and still not writing memory."""

FULL_GRANT: frozenset[Capability] = frozenset(Capability)
"""Everything a client can hold. Never everything the *owner* can do — issuing credentials,
exporting, erasing and restoring stay owner-only however wide a grant is."""


def parse(values: object) -> frozenset[Capability]:
    """Read a stored or submitted grant, dropping anything this version does not know.

    A name from a newer version is discarded rather than kept as an opaque string: an
    unknown grant that survives round trips would eventually be *interpreted* by a version
    that does know it, which is not what the person who approved it agreed to.
    """
    if not isinstance(values, (list, tuple, set, frozenset)):
        return frozenset()
    known = {c.value for c in Capability}
    return frozenset(Capability(v) for v in values if isinstance(v, str) and v in known)


def describe(granted: frozenset[Capability]) -> list[CapabilityInfo]:
    """The granted capabilities, in the declared order, for showing to a person."""
    return [info for info in CAPABILITIES if info.capability in granted]
