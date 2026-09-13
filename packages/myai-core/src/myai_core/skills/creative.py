"""Making pictures, music and video — and saying plainly that this build cannot (spec §49).

Why there is a file here at all when nothing generates anything
--------------------------------------------------------------

The skill tree lists Images, Video, Music and Games. Games is real: designing mechanics,
levels and narrative is prose and arithmetic, so it has a package and a benchmark like any
other text skill, and it is learnable today.

The other three need a model that produces pixels or audio, and that is a different kind of
dependency from anything else in this program:

* **Local generation is real but heavy.** An image model is several gigabytes and effectively
  needs a GPU; a video model needs considerably more of both. Most machines this is meant to
  run on cannot, and a feature that silently does nothing on ordinary hardware is worse than
  one that says so.
* **A cloud API would be easy and would break the promise.** Sending a prompt to somebody
  else's server is precisely the thing this program tells users it does not do. It is not
  a shortcut that can be taken quietly and explained later.

So this file defines what a provider would have to offer, reports honestly that none is
installed, and gives every surface the same sentence to show. When a provider exists it
registers here and the skills become available; until then they say what they need and why
they are not pretending.

Nothing in this module produces media, and nothing in it reaches the network.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable


class Medium(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    MUSIC = "music"


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """What a caller asks a provider for. Deliberately small."""

    medium: Medium
    prompt: str
    seed: int | None = None


@dataclass(frozen=True, slots=True)
class GeneratedFile:
    """Where the result landed. A provider writes to disk; it never returns bytes inline."""

    path: str
    media_type: str
    seed: int | None


@runtime_checkable
class CreativeProvider(Protocol):
    """What something must offer to make this skill real.

    A conforming provider MUST run locally. Any implementation that sends the prompt to a
    remote service is not one of these, whatever else it satisfies: the whole claim of this
    program is that a prompt does not leave the machine, and a provider is not the place to
    make an exception to it.
    """

    @property
    def name(self) -> str: ...

    @property
    def medium(self) -> Medium: ...

    def availability(self) -> tuple[bool, str]:
        """(usable here, why not) — the same shape the inference runtime reports."""
        ...

    def generate(self, request: GenerationRequest, destination: str) -> GeneratedFile: ...


_REGISTERED: dict[Medium, CreativeProvider] = {}


def register(provider: CreativeProvider) -> None:
    """Install a provider for one medium. Nothing in this build calls this."""
    _REGISTERED[provider.medium] = provider


def provider_for(medium: Medium) -> CreativeProvider | None:
    return _REGISTERED.get(medium)


@dataclass(frozen=True, slots=True)
class CreativeStatus:
    """What this build can do for one medium, and what it would take."""

    medium: Medium
    skill_id: str
    available: bool
    detail: str
    needs: str


_WHAT_IT_WOULD_TAKE: dict[Medium, tuple[str, str]] = {
    Medium.IMAGE: (
        "images",
        "A locally run image model — several gigabytes, and in practice a graphics card with "
        "enough memory to hold it. Nothing is sent anywhere to make a picture.",
    ),
    Medium.VIDEO: (
        "video",
        "A locally run video model, which needs considerably more memory and time than an "
        "image model, and a machine that can keep it fed.",
    ),
    Medium.MUSIC: (
        "music",
        "A locally run audio model. Smaller than video, still far larger than the text models "
        "this build ships with.",
    ),
}


def status(medium: Medium) -> CreativeStatus:
    skill_id, needs = _WHAT_IT_WOULD_TAKE[medium]
    provider = provider_for(medium)
    if provider is None:
        return CreativeStatus(
            medium=medium,
            skill_id=skill_id,
            available=False,
            detail=(
                f"No {medium.value} provider is installed, so your AI cannot make "
                f"{medium.value} and this build does not pretend otherwise. It will not be "
                "sent to an online service instead."
            ),
            needs=needs,
        )
    usable, why = provider.availability()
    return CreativeStatus(
        medium=medium,
        skill_id=skill_id,
        available=usable,
        detail=why,
        needs=needs,
    )


def all_statuses() -> list[CreativeStatus]:
    return [status(medium) for medium in Medium]
