"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from myai_core import __version__
from myai_core.api.routes import (
    audit,
    chat,
    commands,
    guide,
    hardware,
    knowledge,
    memory,
    models,
    portable,
    preferences,
    privacy,
    profile,
    projects,
    security,
    skills,
    status,
    storage,
    sync,
)
from myai_core.api.routes import (
    jobs as jobs_routes,
)
from myai_core.api.state import AppState
from myai_core.config import TAURI_ORIGINS, CoreSettings
from myai_core.db.base import make_engine, make_session_factory
from myai_core.db.migrate import upgrade_to_head
from myai_core.db.models import AIProfile
from myai_core.models.download_manager import DownloadManager
from myai_core.models.llama_cpp_provider import LlamaCppProvider
from myai_core.models.provider import ModelProvider
from myai_core.models.runtime import InferenceRuntime
from myai_core.paths import AppPaths, resolve_app_paths
from myai_core.security.auth import LocalAuthPolicy, needs, require_local_auth
from myai_core.security.capabilities import Capability
from myai_core.security.local_token import load_or_create_token
from myai_core.security.storage_checks import repair_secret_storage
from myai_core.skills.jobs import JobManager
from myai_core.skills.trainer import TrainingService
from myai_core.status.service import InternetMonitor, StatusService
from myai_core.sync import install_change_tracking

log = logging.getLogger(__name__)

API_PREFIX = "/api"


# Which capability each part of the API needs (spec §53, §75).
#
# This is the whole access-control surface for a paired client, in one place so it can be
# read at a glance. Two columns because read and write are different asks: the first applies
# to GET and HEAD, the second to everything else, and where a router has no meaningful split
# the two are the same.
#
# A router must appear here to be served at all — there is no "unclassified means allowed".
# `test_capabilities.py` fails if one is missing, so the way this goes wrong is a red test
# rather than a quietly over-broad grant.
#
# Owner-only actions (issuing credentials, exporting, erasing, restoring, turning network
# access on) are enforced inside their routes as well, and stay owner-only however wide a
# client's grant is.
ROUTER_SCOPES: tuple[tuple[Any, Capability, Capability], ...] = (
    (status, Capability.STATUS_READ, Capability.STATUS_READ),
    (hardware, Capability.HARDWARE_READ, Capability.HARDWARE_READ),
    (storage, Capability.HARDWARE_READ, Capability.MODELS_MANAGE),
    (profile, Capability.STATUS_READ, Capability.MEMORY_WRITE),
    (preferences, Capability.STATUS_READ, Capability.MODELS_MANAGE),
    (skills, Capability.SKILLS_READ, Capability.SKILLS_TRAIN),
    (commands, Capability.STATUS_READ, Capability.CHAT_WRITE),
    (guide, Capability.STATUS_READ, Capability.STATUS_READ),
    (jobs_routes, Capability.SKILLS_READ, Capability.SKILLS_TRAIN),
    (audit, Capability.ACTIVITY_READ, Capability.ACTIVITY_READ),
    (privacy, Capability.ACTIVITY_READ, Capability.ACTIVITY_READ),
    (projects, Capability.PROJECTS_READ, Capability.PROJECTS_WRITE),
    (security, Capability.STATUS_READ, Capability.STATUS_READ),
    (models, Capability.MODELS_READ, Capability.MODELS_MANAGE),
    (chat, Capability.CHAT_READ, Capability.CHAT_WRITE),
    (memory, Capability.MEMORY_READ, Capability.MEMORY_WRITE),
    (knowledge, Capability.KNOWLEDGE_READ, Capability.KNOWLEDGE_WRITE),
    (sync, Capability.SYNC, Capability.SYNC),
    (portable, Capability.ACTIVITY_READ, Capability.ACTIVITY_READ),
)


def create_app(
    settings: CoreSettings | None = None,
    paths: AppPaths | None = None,
    *,
    token: str | None = None,
    provider: ModelProvider | None = None,
    download_manager: DownloadManager | None = None,
) -> FastAPI:
    settings = settings or CoreSettings()
    paths = (paths or resolve_app_paths()).ensure()
    allowed_origins = (*TAURI_ORIGINS, *settings.dev_cors_origins)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = make_engine(paths.database_file)
        upgrade_to_head(engine)
        # Every change to a synced row is stamped by a session listener rather than by the
        # services themselves, so a new feature cannot forget to do it (spec §16, §72).
        install_change_tracking()
        resolved_token = token or load_or_create_token(paths.token_file)
        for change in repair_secret_storage(paths):
            log.warning("tightened permissions on a secret that others could read: %s", change)
        started_at = datetime.now(tz=UTC)
        internet = InternetMonitor()
        session_factory = make_session_factory(engine)
        runtime = InferenceRuntime(provider or LlamaCppProvider())
        downloads = download_manager or DownloadManager(session_factory)
        jobs = JobManager(session_factory)
        with session_factory() as startup_session:
            interrupted = JobManager.recover(startup_session)
            # A training run interrupted the same way keeps the best instructions it had
            # found, so the next run for that skill continues from them (spec §40, §74).
            for profile_row in startup_session.scalars(select(AIProfile)).all():
                TrainingService(startup_session, profile_row.ai_id).recover()
            startup_session.commit()
        if interrupted:
            log.warning("%d job(s) were interrupted by a restart and marked failed", interrupted)
        app.state.core = AppState(
            paths=paths,
            engine=engine,
            session_factory=session_factory,
            auth_policy=LocalAuthPolicy.build(resolved_token, allowed_origins),
            started_at=started_at,
            internet=internet,
            status=StatusService(internet, started_at),
            runtime=runtime,
            downloads=downloads,
            jobs=jobs,
            settings=settings,
        )
        app.state.auth_policy = app.state.core.auth_policy
        log.info("myai-core %s ready (data dir: %s)", __version__, paths.data_dir)
        try:
            yield
        finally:
            jobs.shutdown()
            downloads.shutdown()
            listener = app.state.core.network
            if listener is not None:
                # Network access never outlives the service that granted it.
                listener.stop()
                app.state.core.network = None
            runtime.unload()
            engine.dispose()

    app = FastAPI(
        title="MyAI Academy local service",
        version=__version__,
        lifespan=lifespan,
        docs_url=None,  # no interactive docs on a service that carries private data
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    protected = APIRouter(prefix=API_PREFIX, dependencies=[Depends(require_local_auth)])
    for module, read, write in ROUTER_SCOPES:
        protected.include_router(module.router, dependencies=[Depends(needs(read, write))])
    app.include_router(protected)
    # Pairing is the one route that cannot require a credential: a client being paired
    # does not have one yet. It keeps the loopback bind and the Host and Origin checks,
    # and the pairing code itself is the authentication (security/devices.py).
    app.include_router(security.pairing_router, prefix=API_PREFIX)

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:
        # Unauthenticated liveness probe: reveals nothing but "a MyAI core is listening".
        return {"status": "ok", "service": "myai-core", "version": __version__}

    return app
