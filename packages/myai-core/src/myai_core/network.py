"""The opt-in listener that lets a paired device on this network reach the service.

Everything about this is deliberately separate from the loopback listener, which is
unchanged: same application, different socket, different rules.

* **Off unless the user turns it on.** No default, no "for convenience".
* **HTTPS only**, with the host's own certificate. A phone pins its fingerprint at pairing
  time, so there is no certificate authority in the trust path at all
  (:mod:`myai_core.security.host_certificate`).
* **The installation token is refused here.** The master key stays on the machine; a device
  gets a credential of its own by pairing, and that credential can be revoked on its own.
* Turning it on and off is recorded in the audit log, because "can my AI be reached from
  the network" is exactly the kind of thing a user should be able to check after the fact.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any

import uvicorn
from starlette.types import ASGIApp, Receive, Scope, Send

from myai_core.security.auth import LAN_SCOPE_KEY
from myai_core.security.host_certificate import HostCertificate

log = logging.getLogger("myai_core.network")


class NetworkEntrypoint:
    """Wraps the application for the second listener. Two jobs, both load-bearing.

    **It tags every request that arrives here**, so authentication can tell how a caller
    reached us. A middleware rather than a header, because a header is set by whoever is
    talking to us and this fact must not be forgeable.

    **It answers the lifespan protocol itself instead of passing it on.** A second uvicorn
    server would otherwise run the application's startup again, building a second database
    engine, a second job manager and a second copy of the shared state — and replacing the
    running one. The primary listener owns the lifecycle; this one only serves requests.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self._own_lifespan(receive, send)
            return
        if scope["type"] == "http":
            scope = {**scope, LAN_SCOPE_KEY: True}
        await self._app(scope, receive, send)

    @staticmethod
    async def _own_lifespan(receive: Receive, send: Send) -> None:
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return


@dataclass(slots=True)
class NetworkListener:
    """A running HTTPS listener, or the record of one that was asked for and failed."""

    host: str
    port: int
    certificate: HostCertificate
    server: uvicorn.Server
    thread: threading.Thread

    @property
    def running(self) -> bool:
        return self.thread.is_alive() and self.server.started

    def stop(self, timeout: float = 5.0) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=timeout)


def start_listener(
    app: Any,
    *,
    host: str,
    port: int,
    certificate: HostCertificate,
    log_level: str = "warning",
    wait_seconds: float = 5.0,
) -> NetworkListener:
    """Start the HTTPS listener on its own thread and wait until it is actually up."""
    config = uvicorn.Config(
        NetworkEntrypoint(app),
        host=host,
        port=port,
        log_level=log_level,
        ssl_certfile=str(certificate.cert_path),
        ssl_keyfile=str(certificate.key_path),
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="myai-network-listener", daemon=True)
    thread.start()

    deadline = threading.Event()
    waited = 0.0
    while not server.started and thread.is_alive() and waited < wait_seconds:
        deadline.wait(0.05)
        waited += 0.05
    listener = NetworkListener(
        host=host, port=port, certificate=certificate, server=server, thread=thread
    )
    if listener.running:
        log.warning(
            "network access is ON: paired devices can reach this service at https://%s:%s "
            "(certificate fingerprint %s)",
            host,
            port,
            certificate.fingerprint_sha256[:16],
        )
    return listener
