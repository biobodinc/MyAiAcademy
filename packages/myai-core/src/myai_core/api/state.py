"""Objects that live for the lifetime of the app and are shared by request handlers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from myai_core.hardware.models import HardwareReport
from myai_core.models.download_manager import DownloadManager
from myai_core.models.runtime import InferenceRuntime
from myai_core.paths import AppPaths
from myai_core.security.auth import LocalAuthPolicy
from myai_core.skills.jobs import JobManager
from myai_core.status.service import AIState, InternetMonitor, StatusService


@dataclass
class AppState:
    paths: AppPaths
    engine: Engine
    session_factory: sessionmaker[Session]
    auth_policy: LocalAuthPolicy
    started_at: datetime
    internet: InternetMonitor
    status: StatusService
    runtime: InferenceRuntime
    downloads: DownloadManager
    jobs: JobManager
    hardware_cache: HardwareReport | None = None

    def ai_state(self, session: Session) -> AIState:
        """What the AI can do right now: runtime present, model installed, model loaded."""
        from myai_core.hardware.volumes import probe_volumes
        from myai_core.models.service import ModelService
        from myai_core.storage import StorageManager

        available, detail = self.runtime.provider.availability()
        active = ModelService(session, StorageManager(session, probe_volumes)).active_model_id()
        return AIState(
            runtime_available=available,
            runtime_detail=detail,
            active_model_id=active,
            loaded_model_id=self.runtime.provider.loaded_model_id(),
        )
