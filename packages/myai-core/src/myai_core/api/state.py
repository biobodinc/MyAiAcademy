"""Objects that live for the lifetime of the app and are shared by request handlers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from myai_core.hardware.models import HardwareReport
from myai_core.paths import AppPaths
from myai_core.security.auth import LocalAuthPolicy
from myai_core.status.service import InternetMonitor, StatusService


@dataclass
class AppState:
    paths: AppPaths
    engine: Engine
    session_factory: sessionmaker[Session]
    auth_policy: LocalAuthPolicy
    started_at: datetime
    internet: InternetMonitor
    status: StatusService
    hardware_cache: HardwareReport | None = None
