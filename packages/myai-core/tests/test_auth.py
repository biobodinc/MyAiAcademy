"""Authentication and origin/host validation on the local API."""

from fastapi.testclient import TestClient

from myai_core.security.auth import LocalAuthPolicy


def test_missing_token_is_401(anon_client: TestClient) -> None:
    r = anon_client.get("/api/status")
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_wrong_token_is_401(anon_client: TestClient) -> None:
    r = anon_client.get("/api/status", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_healthz_is_public_and_leaks_nothing(anon_client: TestClient) -> None:
    r = anon_client.get("/healthz")
    assert r.status_code == 200
    assert set(r.json()) == {"status", "service", "version"}


def test_docs_are_disabled(anon_client: TestClient) -> None:
    assert anon_client.get("/docs").status_code == 404


def test_valid_token_passes(client: TestClient) -> None:
    assert client.get("/api/status").status_code == 200


def test_foreign_origin_is_rejected_even_with_token(client: TestClient) -> None:
    r = client.get("/api/status", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


def test_tauri_and_dev_origins_allowed(client: TestClient) -> None:
    for origin in ("tauri://localhost", "http://tauri.localhost", "http://localhost:1420"):
        assert client.get("/api/status", headers={"Origin": origin}).status_code == 200


def test_dns_rebinding_host_is_rejected(client: TestClient) -> None:
    r = client.get("/api/status", headers={"Host": "attacker.example"})
    assert r.status_code == 421


def test_cors_preflight_for_unknown_origin_gets_no_allow_header(anon_client: TestClient) -> None:
    r = anon_client.options(
        "/api/status",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}


def test_policy_host_parsing(test_token: str) -> None:
    policy = LocalAuthPolicy.build(test_token, ["tauri://localhost"])
    assert policy.check_host("127.0.0.1:41337")
    assert policy.check_host("localhost")
    assert policy.check_host("[::1]:5000")
    assert not policy.check_host("127.0.0.1.evil.example")
    assert not policy.check_host(None)
    assert policy.check_origin(None)
    assert not policy.check_origin("null")
