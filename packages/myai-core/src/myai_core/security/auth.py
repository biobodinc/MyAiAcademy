"""FastAPI authentication for the local API.

Layers (defence in depth, spec §47/§73):

1. **Loopback bind** – the socket only listens on 127.0.0.1 (``config.CoreSettings``).
2. **Host header check** – rejects DNS-rebinding style requests where a browser was
   tricked into sending a request to ``127.0.0.1`` with a foreign ``Host``.
3. **Origin allow-list** – browsers always send ``Origin`` on cross-origin requests;
   only the packaged Tauri origins and the Vite dev server are accepted. Requests with
   no ``Origin`` header come from native clients (CLI, tests) and pass to step 4.
4. **Bearer token** – the per-installation token compared in constant time.

Scoped capability permissions for third-party apps (spec §48–§50) are Phase 9 and will
layer on top of this rather than replace it.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

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


def require_local_auth(
    request: Request,
    policy: Annotated[LocalAuthPolicy, Depends(get_auth_policy)],
) -> None:
    if not policy.check_host(request.headers.get("host")):
        raise HTTPException(status.HTTP_421_MISDIRECTED_REQUEST, "Unexpected Host header.")
    if not policy.check_origin(request.headers.get("origin")):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Origin not allowed.")

    authorization = request.headers.get("authorization")
    presented: str | None = None
    if authorization and authorization.lower().startswith("bearer "):
        presented = authorization[7:].strip()
    if not tokens_match(presented, policy.token):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Missing or invalid local API token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


LocalAuth = Depends(require_local_auth)
