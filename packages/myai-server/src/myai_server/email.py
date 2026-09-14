"""Sending the one email this server sends, and being honest when it cannot.

There is no email provider wired up yet. The interesting decision is what to do about that,
and the answer is *not* to quietly no-op: a sign-up that reports success while the
verification link goes nowhere is the kind of bug that surfaces weeks later as "nobody can
confirm their address".

So `ConsoleEmailSender` writes the whole message to the log, including the link, and
`configured` is False. Routes read that flag and say plainly in the response that the link was
logged rather than sent, which keeps local development working — you copy the link out of the
log — without anything claiming to have sent mail that did not.

Wiring a real provider means one class implementing `send` and returning True from
`configured`. Nothing else changes.
"""

from __future__ import annotations

import logging
from typing import Protocol
from urllib.parse import quote

log = logging.getLogger(__name__)

VERIFY_SUBJECT = "Confirm your email for MyAI Academy"


class EmailSender(Protocol):
    @property
    def configured(self) -> bool:
        """Whether mail actually leaves this machine."""
        ...

    def send(self, to: str, subject: str, body: str) -> None: ...


class ConsoleEmailSender:
    """Writes mail to the log. For development, and honest about being that."""

    configured = False

    def send(self, to: str, subject: str, body: str) -> None:
        log.warning(
            "No email provider is configured, so this message was not sent. "
            "To: %s\nSubject: %s\n%s",
            to,
            subject,
            body,
        )


def verification_link(base_url: str, token: str) -> str:
    return f"{base_url.rstrip('/')}/verify-email?token={quote(token)}"


def send_verification(sender: EmailSender, *, to: str, base_url: str, token: str) -> None:
    link = verification_link(base_url, token)
    sender.send(
        to,
        VERIFY_SUBJECT,
        (
            "Confirm your email address to finish setting up your MyAI Academy account:\n\n"
            f"{link}\n\n"
            "The link works once and expires in 24 hours.\n\n"
            "If you did not create this account, you can ignore this message — the address "
            "will not be used until someone follows the link."
        ),
    )
