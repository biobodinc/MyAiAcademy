"""What a paired program is allowed to do.

The property that matters most here is the *default*. An access-control list is only worth
anything if the thing it forgot to classify is refused rather than allowed, so that is what
most of these check: a router with no declared capability, a grant that does not cover the
method, a client trying to widen itself, a name from a future version.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from myai_core.api.app import ROUTER_SCOPES, create_app
from myai_core.config import CoreSettings
from myai_core.paths import AppPaths
from myai_core.security.capabilities import (
    BY_NAME,
    CAPABILITIES,
    DEFAULT_GRANT,
    FULL_GRANT,
    MOBILE_GRANT,
    Capability,
    describe,
    parse,
)

TOKEN = "owner-token"


@pytest.fixture
def client(app_paths: AppPaths, tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(CoreSettings(), app_paths, token=TOKEN)
    with TestClient(app, base_url="http://127.0.0.1") as c:
        c.headers.update({"Authorization": f"Bearer {TOKEN}"})
        c.post("/api/profile", json={"name": "Nova"})
        c.put("/api/storage/root", json={"root_path": str(tmp_path / "MyAI")})
        yield c


def _pair(client: TestClient, **body: object) -> tuple[str, dict[str, str]]:
    code = client.post("/api/security/pairing-codes", json={"label": "A tool", **body}).json()[
        "code"
    ]
    issued = client.post(
        "/api/security/pair", json={"code": code, "name": "A tool", "kind": "integration"}
    )
    assert issued.status_code == 201, issued.text
    return issued.json()["device"]["id"], {"Authorization": f"Bearer {issued.json()['token']}"}


# --------------------------------------------------------------------------------------
# The vocabulary itself.
# --------------------------------------------------------------------------------------


def test_every_capability_is_described_in_words_someone_can_act_on() -> None:
    """A consent screen listing bare identifiers asks people to agree to nothing."""
    assert {info.capability for info in CAPABILITIES} == set(Capability)
    for info in CAPABILITIES:
        assert info.title and not info.title.endswith(".")
        assert len(info.detail) > 30, f"{info.capability} is not explained"
        assert ":" not in info.title, "the title should be prose, not the identifier"


def test_anything_that_touches_what_the_user_wrote_is_marked_sensitive() -> None:
    for name in (
        Capability.CHAT_READ,
        Capability.CHAT_WRITE,
        Capability.MEMORY_READ,
        Capability.MEMORY_WRITE,
        Capability.KNOWLEDGE_READ,
        Capability.KNOWLEDGE_WRITE,
        Capability.SYNC,
    ):
        assert BY_NAME[name].sensitive, f"{name} exposes the user's own content"
    # Machine facts are not, or the marking would mean nothing.
    assert not BY_NAME[Capability.HARDWARE_READ].sensitive


def test_the_default_grant_includes_nothing_the_user_has_written() -> None:
    """'Let this thing use my AI' must not also mean 'let it read everything I have said'."""
    for capability in DEFAULT_GRANT:
        assert not BY_NAME[capability].sensitive, f"{capability} should not be granted by default"
    assert Capability.CHAT_READ not in DEFAULT_GRANT
    assert Capability.MEMORY_READ not in DEFAULT_GRANT
    assert DEFAULT_GRANT < MOBILE_GRANT < FULL_GRANT


def test_a_name_from_a_newer_version_is_dropped_rather_than_kept() -> None:
    """An unknown grant that survived would eventually be interpreted by a version that
    knows it — which is not what the person approving it agreed to."""
    assert parse(["memory:read", "telepathy:write"]) == {Capability.MEMORY_READ}
    assert parse("memory:read") == frozenset()
    assert parse(None) == frozenset()
    assert parse([]) == frozenset()


def test_describe_keeps_the_declared_order_so_a_list_reads_the_same_every_time() -> None:
    shown = describe(frozenset({Capability.MEMORY_READ, Capability.STATUS_READ}))
    assert [i.capability for i in shown] == [Capability.STATUS_READ, Capability.MEMORY_READ]


# --------------------------------------------------------------------------------------
# Default deny.
# --------------------------------------------------------------------------------------


def test_every_router_is_classified_before_it_is_served() -> None:
    """A route nobody classified must not be reachable by a scoped client.

    This is the whole reason the table exists in one place: the way it goes wrong should be
    a red test, not a quietly over-broad grant.
    """
    for module, read, write in ROUTER_SCOPES:
        assert hasattr(module, "router"), module
        assert isinstance(read, Capability) and isinstance(write, Capability)
    modules = [module for module, _r, _w in ROUTER_SCOPES]
    assert len(modules) == len({id(m) for m in modules}), "a router is classified twice"


def test_a_client_with_the_default_grant_is_refused_what_it_was_not_given(
    client: TestClient,
) -> None:
    _device_id, headers = _pair(client)

    # What it was given.
    assert client.get("/api/status", headers=headers).status_code == 200
    assert client.get("/api/skills", headers=headers).status_code == 200

    # What it was not, with a message that names the missing grant.
    refused = client.get("/api/memory", headers=headers)
    assert refused.status_code == 403
    assert "memory:read" in refused.json()["detail"]
    assert "not given permission" in refused.json()["detail"]

    assert client.get("/api/chat/conversations", headers=headers).status_code == 403
    assert client.get("/api/knowledge", headers=headers).status_code == 403
    assert client.get("/api/sync", headers=headers).status_code == 403


def test_reading_and_writing_are_separate_asks(client: TestClient) -> None:
    """A tool that summarises your notes rarely needs to rewrite them."""
    _device_id, headers = _pair(client, capabilities=["memory:read"])

    assert client.get("/api/memory", headers=headers).status_code == 200
    written = client.post("/api/memory", json={"content": "sneaked in"}, headers=headers)
    assert written.status_code == 403 and "memory:write" in written.json()["detail"]

    # And the reverse holds: writing does not imply reading.
    _other_id, writer = _pair(client, capabilities=["memory:write"])
    assert client.post("/api/memory", json={"content": "ok"}, headers=writer).status_code in {
        200,
        201,
    }
    assert client.get("/api/memory", headers=writer).status_code == 403


def test_a_client_cannot_widen_its_own_grant(client: TestClient) -> None:
    """The grant is decided by the owner when the code is made, not asked for on redemption."""
    device_id, headers = _pair(client)

    # It cannot set its own capabilities...
    refused = client.put(
        f"/api/security/devices/{device_id}/capabilities",
        json={"capabilities": ["memory:read", "chat:read"]},
        headers=headers,
    )
    assert refused.status_code == 403

    # ...nor issue itself a wider code and redeem that.
    assert (
        client.post(
            "/api/security/pairing-codes", json={"preset": "full"}, headers=headers
        ).status_code
        == 403
    )
    assert client.get("/api/memory", headers=headers).status_code == 403


def test_the_grant_travels_with_the_code_not_the_redemption(client: TestClient) -> None:
    code = client.post(
        "/api/security/pairing-codes", json={"label": "x", "capabilities": ["status:read"]}
    ).json()["code"]
    # The redeeming client asks for nothing and gets exactly what was approved.
    issued = client.post(
        "/api/security/pair", json={"code": code, "name": "x", "kind": "cli"}
    ).json()
    assert issued["device"]["capabilities"] == ["status:read"]


# --------------------------------------------------------------------------------------
# The owner, and changing a grant afterwards.
# --------------------------------------------------------------------------------------


def test_the_owner_is_never_scoped(client: TestClient) -> None:
    """A capability limits programs the owner let in. It does not limit the owner."""
    for path in ("/api/memory", "/api/skills", "/api/sync", "/api/security"):
        assert client.get(path).status_code == 200, path


def test_narrowing_a_grant_takes_effect_on_the_next_request(client: TestClient) -> None:
    device_id, headers = _pair(client, preset="full")
    assert client.get("/api/memory", headers=headers).status_code == 200

    client.put(
        f"/api/security/devices/{device_id}/capabilities", json={"capabilities": ["status:read"]}
    )
    assert client.get("/api/memory", headers=headers).status_code == 403
    assert client.get("/api/status", headers=headers).status_code == 200


def test_widening_a_grant_also_takes_effect_at_once(client: TestClient) -> None:
    device_id, headers = _pair(client)
    assert client.get("/api/memory", headers=headers).status_code == 403

    client.put(
        f"/api/security/devices/{device_id}/capabilities",
        json={"capabilities": ["status:read", "memory:read"]},
    )
    assert client.get("/api/memory", headers=headers).status_code == 200


def test_changing_a_grant_is_written_down_with_what_changed(client: TestClient) -> None:
    device_id, _headers = _pair(client)
    client.put(
        f"/api/security/devices/{device_id}/capabilities",
        json={"capabilities": ["status:read", "chat:read"]},
    )
    events = client.get("/api/audit", params={"category": "security"}).json()
    changed = [e for e in events if e["action"] == "device_capabilities_changed"]
    assert changed, "a permission change has to be answerable later"
    assert "chat:read" in changed[0]["details"]["added"]
    assert changed[0]["details"]["removed"], "what was taken away is recorded too"


def test_a_revoked_client_cannot_be_given_permissions_instead_of_being_paired_again(
    client: TestClient,
) -> None:
    device_id, _headers = _pair(client)
    client.post(f"/api/security/devices/{device_id}/revoke", json={"reason": "lost"})
    refused = client.put(
        f"/api/security/devices/{device_id}/capabilities", json={"capabilities": ["status:read"]}
    )
    assert refused.status_code == 409 and "revoked" in refused.json()["detail"]


def test_the_capability_list_is_offered_so_a_consent_screen_can_be_built(
    client: TestClient,
) -> None:
    listed = client.get("/api/security/capabilities").json()
    assert len(listed) == len(CAPABILITIES)
    assert {c["capability"] for c in listed} == {c.value for c in Capability}
    assert all(c["title"] and c["detail"] for c in listed)
    assert any(c["sensitive"] for c in listed)


def test_an_unknown_preset_is_refused_rather_than_treated_as_empty(client: TestClient) -> None:
    """Silently granting nothing would look like a working pairing that then fails oddly."""
    refused = client.post("/api/security/pairing-codes", json={"preset": "everything"})
    assert refused.status_code == 400 and "Unknown preset" in refused.json()["detail"]


def test_the_mobile_preset_is_what_a_phone_needs_and_no_more(client: TestClient) -> None:
    _device_id, headers = _pair(client, preset="mobile")
    assert client.get("/api/status", headers=headers).status_code == 200
    assert client.get("/api/memory", headers=headers).status_code == 200
    assert client.get("/api/sync", headers=headers).status_code == 200
    # Not the knowledge files, and not rewriting what the AI remembers.
    assert client.get("/api/knowledge", headers=headers).status_code == 403
    assert client.post("/api/memory", json={"content": "x"}, headers=headers).status_code == 403
