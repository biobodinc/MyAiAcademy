"""The opt-in network listener, against a real TLS socket.

None of this is mocked: a real HTTPS server is started on a real port with the certificate
the host mints, and a real client connects to it. The properties under test are the ones
that would matter if someone else were on the same Wi-Fi:

* the connection is encrypted, and the certificate is exactly the one that was pinned;
* a client pinned to a different certificate refuses to talk at all;
* the installation token — the master key — is refused over the network;
* a paired credential works, and revoking it stops the device.
"""

from __future__ import annotations

import json
import socket
import ssl
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from myai_core.api.app import create_app
from myai_core.config import CoreSettings
from myai_core.network import start_listener
from myai_core.paths import AppPaths
from myai_core.security.host_certificate import fingerprint_of_pem, load_or_create

TOKEN = "owner-token"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture
def host(app_paths: AppPaths, tmp_path: Path) -> Iterator[dict[str, object]]:
    """A service with both listeners: loopback for the owner, HTTPS for devices."""
    app = create_app(CoreSettings(), app_paths, token=TOKEN)
    with TestClient(app, base_url="http://127.0.0.1") as local:
        local.headers.update({"Authorization": f"Bearer {TOKEN}"})
        local.post("/api/profile", json={"name": "Nova"})
        local.put("/api/storage/root", json={"root_path": str(tmp_path / "MyAI")})

        certificate = load_or_create(app_paths.data_dir, addresses=["127.0.0.1"])
        port = _free_port()
        listener = start_listener(
            app, host="127.0.0.1", port=port, certificate=certificate, wait_seconds=10
        )
        assert listener.running, "the HTTPS listener did not start"
        try:
            yield {
                "local": local,
                "base": f"https://127.0.0.1:{port}/api",
                "fingerprint": certificate.fingerprint_sha256,
                "cert": certificate.cert_path,
            }
        finally:
            listener.stop()


def _pinned_client(host: dict[str, object]) -> httpx.Client:
    """A client that trusts exactly this host's certificate and nothing else.

    This is what a phone does with the fingerprint from the QR code. Here the pin is
    expressed by trusting that one certificate as the only root, which fails in the same
    way — no other certificate can satisfy it.
    """
    context = ssl.create_default_context(cafile=str(host["cert"]))
    return httpx.Client(verify=context, base_url=str(host["base"]))


def _pair(host: dict[str, object], name: str = "Phone") -> tuple[str, str]:
    local: TestClient = host["local"]  # type: ignore[assignment]
    code = local.post("/api/security/pairing-codes", json={"label": name}).json()["code"]
    with _pinned_client(host) as client:
        issued = client.post("/security/pair", json={"code": code, "name": name, "kind": "mobile"})
    assert issued.status_code == 201, issued.text
    body = issued.json()
    return body["device"]["id"], body["token"]


def test_the_connection_is_encrypted_with_the_certificate_that_was_pinned(
    host: dict[str, object],
) -> None:
    pem = ssl.get_server_certificate(
        ("127.0.0.1", int(str(host["base"]).split(":")[2].split("/")[0]))
    )
    assert fingerprint_of_pem(pem.encode()) == host["fingerprint"]


def test_a_client_pinned_to_something_else_refuses_to_talk(
    host: dict[str, object], tmp_path: Path
) -> None:
    """Pinning is only worth anything if the wrong certificate actually fails."""
    other = load_or_create(tmp_path / "someone-else", addresses=["127.0.0.1"])
    assert other.fingerprint_sha256 != host["fingerprint"]
    context = ssl.create_default_context(cafile=str(other.cert_path))
    with (
        httpx.Client(verify=context, base_url=str(host["base"])) as client,
        pytest.raises(httpx.ConnectError),
    ):
        client.get("/status")


def test_an_unverified_client_is_not_what_we_rely_on(host: dict[str, object]) -> None:
    """Sanity: the service is reachable, so the refusal above was the pin and not the port."""
    with httpx.Client(verify=False, base_url=str(host["base"])) as client:
        # Reachable, and still refuses a request with no credential.
        assert client.get("/status").status_code == 401


def test_the_installation_token_is_refused_over_the_network(host: dict[str, object]) -> None:
    """The master key stays on the machine. A device pairs for a credential of its own."""
    with _pinned_client(host) as client:
        res = client.get("/status", headers={"Authorization": f"Bearer {TOKEN}"})
    assert res.status_code == 403
    assert "cannot be used from the network" in res.json()["detail"]

    # The same token still works on loopback, where it belongs.
    local: TestClient = host["local"]  # type: ignore[assignment]
    assert local.get("/api/status").status_code == 200


def test_a_paired_device_works_over_the_network_until_it_is_revoked(
    host: dict[str, object],
) -> None:
    device_id, token = _pair(host)
    with _pinned_client(host) as client:
        headers = {"Authorization": f"Bearer {token}"}
        assert client.get("/status", headers=headers).status_code == 200
        overview = client.get("/security", headers=headers).json()
        assert overview["caller_is_owner"] is False and overview["caller_name"] == "Phone"

        local: TestClient = host["local"]  # type: ignore[assignment]
        local.post(f"/api/security/devices/{device_id}/revoke", json={"reason": "lost"})

        assert client.get("/status", headers=headers).status_code == 401


def test_a_device_cannot_grant_itself_more_from_the_network(host: dict[str, object]) -> None:
    _device_id, token = _pair(host)
    with _pinned_client(host) as client:
        headers = {"Authorization": f"Bearer {token}"}
        assert client.post("/security/pairing-codes", json={}, headers=headers).status_code == 403
        assert client.post("/privacy/export", json={}, headers=headers).status_code == 403


def test_a_phone_addresses_this_machine_by_its_network_address(host: dict[str, object]) -> None:
    """The loopback listener insists on a loopback Host header; this one cannot.

    A phone reaches the host at 192.168.x.y, so the Host header is legitimately not
    localhost. That relaxation must apply only to this listener, which the loopback tests
    covering the same header prove.
    """
    _device_id, token = _pair(host)
    with _pinned_client(host) as client:
        res = client.get(
            "/status",
            headers={"Authorization": f"Bearer {token}", "Host": "myai.local"},
        )
    assert res.status_code == 200


def test_network_access_is_off_until_asked_for_and_is_recorded_both_ways(
    app_paths: AppPaths, tmp_path: Path
) -> None:
    """Whether the AI is reachable from the network is a fact the log should carry."""
    app = create_app(CoreSettings(), app_paths, token=TOKEN)
    with TestClient(app, base_url="http://127.0.0.1") as local:
        local.headers.update({"Authorization": f"Bearer {TOKEN}"})
        local.post("/api/profile", json={"name": "Nova"})

        off = local.get("/api/security").json()["network"]
        assert off["enabled"] is False
        assert "listens on this machine only" in off["detail"]
        # No invite can exist while nothing can reach the machine.
        assert local.post("/api/security/pairing-invite", json={}).status_code == 409

        port = _free_port()
        on = local.post("/api/security/network", json={"enabled": True, "port": port}).json()
        assert on["enabled"] is True and on["port"] == port
        assert len(on["certificate_fingerprint"]) == 64
        assert on["certificate_fingerprint_groups"].count(" ") > 8

        invite = local.post("/api/security/pairing-invite", json={"label": "Phone"}).json()
        assert invite["certificate_fingerprint"] == on["certificate_fingerprint"]
        assert invite["port"] == port
        payload = json.loads(invite["payload"])
        assert payload["fp"] == on["certificate_fingerprint"]
        assert payload["code"] == invite["code"] and payload["port"] == port

        assert (
            local.post("/api/security/network", json={"enabled": False}).json()["enabled"] is False
        )

        actions = [
            e["action"] for e in local.get("/api/audit", params={"category": "security"}).json()
        ]
        assert "network_access_enabled" in actions
        assert "network_access_disabled" in actions


def test_a_device_cannot_turn_network_access_on(host: dict[str, object]) -> None:
    _device_id, token = _pair(host)
    with _pinned_client(host) as client:
        res = client.post(
            "/security/network",
            json={"enabled": True},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res.status_code == 403


def test_the_second_listener_shares_the_first_one_s_state(host: dict[str, object]) -> None:
    """One service, two doors — not two services.

    A second uvicorn server runs the same application object, and would by default run its
    startup again: a second database engine, a second job manager, and a replacement for
    the shared state the first listener is using. The listener answers the lifespan
    protocol itself instead, so there is exactly one of everything.
    """
    local: TestClient = host["local"]  # type: ignore[assignment]
    core = local.app.state.core  # type: ignore[attr-defined]

    _device_id, token = _pair(host)
    with _pinned_client(host) as client:
        client.get("/status", headers={"Authorization": f"Bearer {token}"})

    assert local.app.state.core is core, "the network listener replaced the running state"
