"""Dependencies: the transaction boundary, and who is calling.

The session dependency owns the transaction. Services flush but never commit, so a request
that raises anywhere — including inside a route, after the service returned — rolls the whole
thing back. Half an account is not a state this server can end up in.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as DbSession

from myai_server.models import Account, Session
from myai_server.services import AccountService
from myai_server.state import ServerState


def get_state(request: Request) -> ServerState:
    state: ServerState = request.app.state.server
    return state


StateDep = Annotated[ServerState, Depends(get_state)]


def get_session(state: StateDep) -> Iterator[DbSession]:
    """One transaction per request, kept open until the response is decided.

    The `HTTPException` branch is the interesting one, and it is deliberate. Two of the things
    this server must record happen *only* on requests that fail: a wrong password, and a wrong
    pairing code. Rolling those back along with everything else would mean a guesser's attempts
    were never counted and never logged — the attempt limit in `services.MAX_PAIRING_ATTEMPTS`
    would reset on every guess, which is the same as not having one.

    An `HTTPException` is a route deciding the outcome on purpose, having checked first; the
    services here mutate nothing on the way to raising one, apart from those records. A genuine
    error is different — nobody chose it, nothing is known about how far it got — so it still
    rolls back.
    """
    session = state.session_factory()
    try:
        yield session
        session.commit()
    except HTTPException:
        session.commit()
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


SessionDep = Annotated[DbSession, Depends(get_session)]


def client_ip(request: Request) -> str | None:
    """The caller's address, as the server actually saw it.

    Deliberately not read from `X-Forwarded-For`: anyone can send that header, and an audit
    log that records whatever the client claimed is worse than one that records nothing. Behind
    a reverse proxy, run uvicorn with `--proxy-headers --forwarded-allow-ips=<the proxy>` so
    the address is rewritten by something that knows which hop to trust.
    """
    return request.client.host if request.client else None


def get_service(session: SessionDep, request: Request) -> AccountService:
    return AccountService(
        session,
        ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )


ServiceDep = Annotated[AccountService, Depends(get_service)]


def _bearer(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token.strip() else None


def require_session(request: Request, service: ServiceDep) -> Session:
    token = _bearer(request)
    row = service.authenticate(token) if token else None
    if row is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Sign in to continue.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return row


SessionAuthDep = Annotated[Session, Depends(require_session)]


def require_account(auth: SessionAuthDep, service: ServiceDep) -> Account:
    account = service.get_account(auth.account_id)
    if account is None:
        # The session outlived the account it belonged to. Nothing to do but refuse it.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue.")
    return account


AccountDep = Annotated[Account, Depends(require_account)]
