"""FastAPI authentication for the local API.

Layers (defence in depth, spec §47/§73):

1. **Loopback bind** – the socket only listens on 127.0.0.1 (``config.CoreSettings``).
2. **Host header check** – rejects DNS-rebinding style requests where a browser was
   tricked into sending a request to ``127.0.0.1`` with a foreign ``Host``.
3. **Origin allow-list** – browsers always send ``Origin`` on cross-origin requests;
   only the packaged Tauri origins and the Vite dev server are accepted. Requests with
   no ``Origin`` header come from native clients (CLI, tests) and pass to step 4.
4. **Bearer token** – either the per-installation token, compared in constant time, or a
   credential issued to a paired client (:mod:`myai_core.security.devices`). Both
   identify a *caller*, which is recorded with what it did; a paired client's credential
   can be revoked on its own, and revocation takes effect on its next request.

Scoped capability permissions for third-party apps (spec §48–§50) are Phase 9 and will
layer on top of this rather than replace it.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from myai_core.security.devices import OWNER_CALLER, Caller, DeviceService
from myai_core.security.local_token import tokens_match

_ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost", "[::1]"})


@dataclass(frozen=True, slots=True)
class LocalAuthPolicy:
    token: str
    allowed_origins: frozenset[str]

    @classmethod
    def build(cls, token: str, origins: Iterable[str]) -> LocalAuthPolicy:
        return cls(token=token, allowed_origins=frozenset(origins))

    def check_host(self, host_header: str | None) -> bool:
        if not host_header:
            return False
        host = (
            host_header.rsplit(":", 1)[0]
            if not host_header.startswith("[")
            else (host_header.split("]")[0] + "]")
        )
        return host in _ALLOWED_HOSTS

    def check_origin(self, origin: str | None) -> bool:
        # No Origin: native client (not a browser). Browsers cannot omit it cross-origin.
        return origin is None or origin in self.allowed_origins


def get_auth_policy(request: Request) -> LocalAuthPolicy:
    policy: LocalAuthPolicy | None = getattr(request.app.state, "auth_policy", None)
    if policy is None:  # pragma: no cover - programming error, not a runtime path
        raise RuntimeError("auth policy not configured on app.state")
    return policy


def bearer_token(request: Request) -> str | None:
    authorization = request.headers.get("authorization")
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return None


def require_local_origin(
    request: Request,
    policy: Annotated[LocalAuthPolicy, Depends(get_auth_policy)],
) -> None:
    """Steps 2 and 3 without the credential, for the one route that cannot have one.

    Pairing has to be reachable by a client that holds nothing yet, but it must not become
    a hole in the browser protections: a web page must not be able to walk a user through
    pairing itself.
    """
    if not policy.check_host(request.headers.get("host")):
        raise HTTPException(status.HTTP_421_MISDIRECTED_REQUEST, "Unexpected Host header.")
    if not policy.check_origin(request.headers.get("origin")):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Origin not allowed.")


def require_local_auth(
    request: Request,
    policy: Annotated[LocalAuthPolicy, Depends(get_auth_policy)],
) -> Caller:
    """Authenticate the request and return who made it.

    The installation token is the owner's own processes. Anything else is checked against
    the paired clients, so a revoked client stops working from its next request without
    the owner having to rotate their own token.
    """
    require_local_origin(request, policy)
    presented = bearer_token(request)
    if tokens_match(presented, policy.token):
        request.state.caller = OWNER_CALLER
        return OWNER_CALLER
    caller = _paired_caller(request, presented)
    if caller is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Missing or invalid local API credential.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    request.state.caller = caller
    return caller


def _paired_caller(request: Request, presented: str | None) -> Caller | None:
    """Look the credential up among the paired clients.

    This opens its own short session rather than taking the request's, so that this module
    stays independent of the API's dependency graph. The owner's token never reaches here,
    so the common path costs no query at all.
    """
    if presented is None:
        return None
    state = getattr(request.app.state, "core", None)
    if state is None:  # pragma: no cover - programming error, not a runtime path
        raise RuntimeError("app state not configured")
    with state.session_factory() as session:
        device = DeviceService(session).resolve(presented)
        if device is None:
            return None
        caller = Caller(device_id=device.id, name=device.name, is_owner=False)
        session.commit()  # resolve() records that the client was seen
        return caller


def get_caller(request: Request) -> Caller:
    """The authenticated caller. Requires ``LocalAuth`` on the route or router."""
    caller: Caller | None = getattr(request.state, "caller", None)
    if caller is None:  # pragma: no cover - a route without LocalAuth is a wiring error
        raise RuntimeError("no authenticated caller on request.state")
    return caller


CallerDep = Annotated[Caller, Depends(get_caller)]
LocalAuth = Depends(require_local_auth)
LocalOrigin = Depends(require_local_origin)
