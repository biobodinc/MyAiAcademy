"""What one running server holds."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from myai_server.config import ServerSettings
from myai_server.email import EmailSender


@dataclass(slots=True)
class ServerState:
    engine: Engine
    session_factory: sessionmaker
    settings: ServerSettings
    email: EmailSender
