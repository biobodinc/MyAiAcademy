"""The account server, assembled.

Unlike `myai_core`, there is no blanket authentication dependency here. This server's whole
job includes the routes someone uses *before* they have a credential — signing up, signing in,
confirming an address, redeeming a pairing code — so a global guard would have to be punched
through four times, and a guard with four holes is not one. Each route that needs a caller
asks for one instead, through `AccountDep` or `SessionAuthDep`, and a route that does not ask
is unauthenticated on purpose and says so in its docstring.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine

from myai_server.api.routes import accounts, devices
from myai_server.config import ServerSettings
from myai_server.db import create_engine_from_env, init_db, make_session_factory
from myai_server.email import ConsoleEmailSender, EmailSender
from myai_server.state import ServerState

log = logging.getLogger(__name__)

API_PREFIX = "/api"


def create_app(
    settings: ServerSettings | None = None,
    *,
    engine: Engine | None = None,
    email: EmailSender | None = None,
) -> FastAPI:
    settings = settings or ServerSettings()
    sender = email or ConsoleEmailSender()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if engine is not None:
            live_engine, session_factory = engine, make_session_factory(engine)
        else:
            live_engine, session_factory = create_engine_from_env(settings)
        init_db(live_engine)
        app.state.server = ServerState(
            engine=live_engine,
            session_factory=session_factory,
            settings=settings,
            email=sender,
        )
        if not sender.configured:
            log.warning(
                "No email provider is configured. Verification links will be written to this "
                "log instead of being sent."
            )
        try:
            yield
        finally:
            if engine is None:
                # Only dispose what we opened. An injected engine belongs to the caller, and
                # in tests that caller is still using it after the app shuts down.
                live_engine.dispose()

    app = FastAPI(
        title="MyAI Academy account server",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,  # no interactive docs on a service that holds account records
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,  # the session token travels in Authorization, not a cookie
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    api = APIRouter(prefix=API_PREFIX)
    api.include_router(accounts.router)
    api.include_router(devices.router)
    api.include_router(devices.pairing_router)
    app.include_router(api)

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:
        return {"status": "ok", "service": "myai-server"}

    return app
