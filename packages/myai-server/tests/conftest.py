"""Shared fixtures: a real app, a real database, and a mailbox we can read."""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from myai_server.app import create_app
from myai_server.config import ServerSettings
from myai_server.db import init_db, make_session_factory


@dataclass
class Sent:
    to: str
    subject: str
    body: str


@dataclass
class RecordingEmailSender:
    """Stands in for a provider and keeps what it was asked to send.

    `configured` is True so the routes take the same path they would in production; the
    console sender's honest "this was not sent" wording is covered separately.
    """

    configured: bool = True
    outbox: list[Sent] = field(default_factory=list)

    def send(self, to: str, subject: str, body: str) -> None:
        self.outbox.append(Sent(to=to, subject=subject, body=body))

    @property
    def last_link(self) -> str:
        lines = self.outbox[-1].body.splitlines()
        return next(line for line in lines if line.startswith("http")).strip()

    @property
    def last_token(self) -> str:
        return parse_qs(urlparse(self.last_link).query)["token"][0]


@pytest.fixture
def engine():
    # StaticPool keeps every connection pointed at the same in-memory database; without it
    # each checkout gets a fresh empty one and nothing persists between requests.
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    init_db(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def mailbox() -> RecordingEmailSender:
    return RecordingEmailSender()


@pytest.fixture
def client(engine, mailbox) -> TestClient:
    settings = ServerSettings(base_url="https://example.com")
    with TestClient(create_app(settings, engine=engine, email=mailbox)) as c:
        yield c


@pytest.fixture
def session_factory(engine):
    return make_session_factory(engine)


PASSWORD = "correct horse battery staple"


@pytest.fixture
def account(client) -> dict:
    """A signed-up account, with its session token."""
    response = client.post(
        "/api/accounts/sign-up", json={"email": "owner@example.com", "password": PASSWORD}
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def auth(account) -> dict[str, str]:
    return {"Authorization": f"Bearer {account['token']}"}


@pytest.fixture
def in_memory_db(engine):
    """A session on the throwaway database, for tests that call services directly."""
    return make_session_factory(engine)()
