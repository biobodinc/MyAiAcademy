"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    preferences,
    privacy,
    profile,
    skills,
    status,
    storage,
)
from myai_core.api.routes import (
    jobs as jobs_routes,
)
from myai_core.api.state import AppState
from myai_core.config import TAURI_ORIGINS, CoreSettings
from myai_core.db.base import make_engine, make_session_factory
from myai_core.db.migrate import upgrade_to_head
from myai_core.models.download_manager import DownloadManager
from myai_core.models.llama_cpp_provider import LlamaCppProvider
from myai_core.models.provider import ModelProvider
from myai_core.models.runtime import InferenceRuntime
from myai_core.paths import AppPaths, resolve_app_paths
from myai_core.security.auth import LocalAuthPolicy, require_local_auth
from myai_core.security.local_token import load_or_create_token
from myai_core.skills.jobs import JobManager
from myai_core.status.service import InternetMonitor, StatusService

log = logging.getLogger(__name__)

API_PREFIX = "/api"


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
        resolved_token = token or load_or_create_token(paths.token_file)
        started_at = datetime.now(tz=UTC)
        internet = InternetMonitor()
        session_factory = make_session_factory(engine)
        runtime = InferenceRuntime(provider or LlamaCppProvider())
        downloads = download_manager or DownloadManager(session_factory)
        jobs = JobManager(session_factory)
        with session_factory() as startup_session:
            interrupted = JobManager.recover(startup_session)
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
        )
        app.state.auth_policy = app.state.core.auth_policy
        log.info("myai-core %s ready (data dir: %s)", __version__, paths.data_dir)
        try:
            yield
        finally:
            jobs.shutdown()
            downloads.shutdown()
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
    for module in (
        status,
        hardware,
        storage,
        profile,
        preferences,
        skills,
        commands,
        guide,
        jobs_routes,
        audit,
        privacy,
        models,
        chat,
        memory,
        knowledge,
    ):
        protected.include_router(module.router)
    app.include_router(protected)

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:
        # Unauthenticated liveness probe: reveals nothing but "a MyAI core is listening".
        return {"status": "ok", "service": "myai-core", "version": __version__}

    return app
