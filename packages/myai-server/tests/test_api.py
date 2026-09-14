"""The account API, exercised through real HTTP requests.

These go through the app rather than calling the service directly, because most of what could
go wrong here is in the wiring: a route that forgets to require a caller, an error that says
too much, a token that keeps working after it should have stopped.
"""

from __future__ import annotations

from myai_server.services import MAX_PAIRING_ATTEMPTS

from .conftest import PASSWORD


def pair_device(client, code, device_id="inst_abc", name="Laptop"):
    return client.post(
        "/api/devices/pair",
        json={"code": code, "device_id": device_id, "device_name": name},
    )


# --- signing up -------------------------------------------------------------------------------


def test_sign_up_creates_an_account_and_signs_it_in(client, mailbox):
    response = client.post(
        "/api/accounts/sign-up", json={"email": "new@example.com", "password": PASSWORD}
    )

    assert response.status_code == 201
    body = response.json()
    assert len(body["account"]["account_id"]) == 16
    assert body["account"]["email"] == "new@example.com"
    assert body["account"]["email_verified"] is False
    assert body["verification_email_sent"] is True
    assert mailbox.outbox[-1].to == "new@example.com"

    me = client.get("/api/accounts/me", headers={"Authorization": f"Bearer {body['token']}"})
    assert me.status_code == 200


def test_sign_up_never_returns_the_verification_token(client):
    """The link is a bearer secret. It goes to the inbox and nowhere else."""
    response = client.post(
        "/api/accounts/sign-up", json={"email": "new@example.com", "password": PASSWORD}
    )
    assert "verification" not in response.text.lower().replace("verification_email_sent", "")


def test_sign_up_refuses_a_duplicate_address(client, account):
    response = client.post(
        "/api/accounts/sign-up", json={"email": "owner@example.com", "password": PASSWORD}
    )
    assert response.status_code == 409


def test_sign_up_normalises_the_address(client):
    client.post(
        "/api/accounts/sign-up", json={"email": "Mixed@Example.com", "password": PASSWORD}
    )
    again = client.post(
        "/api/accounts/sign-up", json={"email": "mixed@example.com", "password": PASSWORD}
    )
    assert again.status_code == 409


def test_sign_up_rejects_a_short_password(client):
    response = client.post(
        "/api/accounts/sign-up", json={"email": "new@example.com", "password": "short"}
    )
    assert response.status_code == 422


def test_sign_up_rejects_a_malformed_address(client):
    response = client.post(
        "/api/accounts/sign-up", json={"email": "not-an-address", "password": PASSWORD}
    )
    assert response.status_code == 422


# --- signing in -------------------------------------------------------------------------------


def test_sign_in_with_the_right_password(client, account):
    response = client.post(
        "/api/accounts/sign-in", json={"email": "owner@example.com", "password": PASSWORD}
    )
    assert response.status_code == 200
    assert response.json()["account"]["account_id"] == account["account"]["account_id"]


def test_sign_in_with_the_wrong_password_is_refused(client, account):
    response = client.post(
        "/api/accounts/sign-in", json={"email": "owner@example.com", "password": "wrong" * 3}
    )
    assert response.status_code == 401


def test_an_unknown_address_is_refused_identically(client, account):
    """The response must not distinguish "no such account" from "wrong password"."""
    wrong_password = client.post(
        "/api/accounts/sign-in", json={"email": "owner@example.com", "password": "wrong" * 3}
    )
    no_account = client.post(
        "/api/accounts/sign-in", json={"email": "nobody@example.com", "password": "wrong" * 3}
    )
    assert wrong_password.status_code == no_account.status_code == 401
    assert wrong_password.json() == no_account.json()


def test_signing_out_stops_the_token_working(client, account, auth):
    assert client.post("/api/accounts/sign-out", headers=auth).status_code == 200
    assert client.get("/api/accounts/me", headers=auth).status_code == 401


def test_protected_routes_refuse_a_missing_or_junk_token(client):
    assert client.get("/api/accounts/me").status_code == 401
    assert client.get("/api/accounts/me", headers={"Authorization": "Bearer no"}).status_code == 401
    assert client.get("/api/accounts/me", headers={"Authorization": "Basic ab"}).status_code == 401


# --- confirming an address --------------------------------------------------------------------


def test_verifying_an_address(client, account, mailbox):
    response = client.post("/api/accounts/verify-email", json={"token": mailbox.last_token})

    assert response.status_code == 200
    assert response.json()["email_verified"] is True


def test_a_verification_link_works_once(client, account, mailbox):
    token = mailbox.last_token
    assert client.post("/api/accounts/verify-email", json={"token": token}).status_code == 200
    assert client.post("/api/accounts/verify-email", json={"token": token}).status_code == 400


def test_a_forged_verification_token_is_refused(client, account):
    response = client.post("/api/accounts/verify-email", json={"token": "made up"})
    assert response.status_code == 400


def test_resending_gives_a_working_link(client, account, auth, mailbox):
    assert client.post("/api/accounts/resend-verification", headers=auth).status_code == 200
    assert len(mailbox.outbox) == 2

    response = client.post("/api/accounts/verify-email", json={"token": mailbox.last_token})
    assert response.status_code == 200


def test_the_verification_link_points_at_the_configured_site(client, account, mailbox):
    assert mailbox.last_link.startswith("https://example.com/verify-email?token=")


# --- changing a password ----------------------------------------------------------------------


def test_changing_a_password_ends_every_other_session(client, account, auth):
    other = client.post(
        "/api/accounts/sign-in", json={"email": "owner@example.com", "password": PASSWORD}
    ).json()["token"]
    other_auth = {"Authorization": f"Bearer {other}"}
    assert client.get("/api/accounts/me", headers=other_auth).status_code == 200

    response = client.post(
        "/api/accounts/change-password",
        headers=auth,
        json={"current_password": PASSWORD, "new_password": "a different long password"},
    )

    assert response.status_code == 200
    # The session that made the change is replaced, not kept alive.
    assert client.get("/api/accounts/me", headers=auth).status_code == 401
    assert client.get("/api/accounts/me", headers=other_auth).status_code == 401
    fresh = {"Authorization": f"Bearer {response.json()['token']}"}
    assert client.get("/api/accounts/me", headers=fresh).status_code == 200


def test_the_new_password_is_the_one_that_works(client, account, auth):
    client.post(
        "/api/accounts/change-password",
        headers=auth,
        json={"current_password": PASSWORD, "new_password": "a different long password"},
    )
    old = client.post(
        "/api/accounts/sign-in", json={"email": "owner@example.com", "password": PASSWORD}
    )
    new = client.post(
        "/api/accounts/sign-in",
        json={"email": "owner@example.com", "password": "a different long password"},
    )
    assert old.status_code == 401
    assert new.status_code == 200


def test_changing_a_password_needs_the_current_one(client, account, auth):
    response = client.post(
        "/api/accounts/change-password",
        headers=auth,
        json={"current_password": "not it at all", "new_password": "a different long password"},
    )
    assert response.status_code == 403


# --- pairing a device -------------------------------------------------------------------------


def test_pairing_a_device_gives_it_its_own_session(client, account, auth):
    code = client.post("/api/devices/pairing-codes", headers=auth).json()["code"]

    paired = client.post(
        "/api/devices/pair",
        json={"code": code, "device_id": "inst_abc123", "device_name": "My Laptop"},
    )

    assert paired.status_code == 201
    assert paired.json()["account"]["account_id"] == account["account"]["account_id"]
    assert paired.json()["token"] != account["token"]

    device_auth = {"Authorization": f"Bearer {paired.json()['token']}"}
    assert client.get("/api/accounts/me", headers=device_auth).status_code == 200


def test_a_pairing_code_works_once(client, account, auth):
    code = client.post("/api/devices/pairing-codes", headers=auth).json()["code"]
    first = client.post(
        "/api/devices/pair", json={"code": code, "device_id": "inst_one", "device_name": "One"}
    )
    second = client.post(
        "/api/devices/pair", json={"code": code, "device_id": "inst_two", "device_name": "Two"}
    )
    assert first.status_code == 201
    assert second.status_code == 403


def test_a_wrong_code_is_refused(client):
    response = client.post(
        "/api/devices/pair", json={"code": "00000000", "device_id": "inst_x", "device_name": "X"}
    )
    assert response.status_code == 403


def test_guessing_burns_the_live_code(client, account, auth):
    """A code must not survive unlimited guesses just because eight digits is a big number."""
    code = client.post("/api/devices/pairing-codes", headers=auth).json()["code"]
    wrong = "00000000" if code != "00000000" else "11111111"

    for _ in range(MAX_PAIRING_ATTEMPTS):
        client.post(
            "/api/devices/pair",
            json={"code": wrong, "device_id": "inst_guess", "device_name": "G"},
        )

    response = client.post(
        "/api/devices/pair", json={"code": code, "device_id": "inst_real", "device_name": "R"}
    )
    assert response.status_code == 403


def test_pairing_codes_need_a_signed_in_caller(client):
    assert client.post("/api/devices/pairing-codes").status_code == 401


def test_a_malformed_code_is_rejected_before_it_reaches_the_database(client):
    response = client.post(
        "/api/devices/pair", json={"code": "abc", "device_id": "inst_x", "device_name": "X"}
    )
    assert response.status_code == 422


# --- managing devices -------------------------------------------------------------------------


def test_listing_devices(client, account, auth):
    code = client.post("/api/devices/pairing-codes", headers=auth).json()["code"]
    client.post(
        "/api/devices/pair",
        json={"code": code, "device_id": "inst_abc", "device_name": "My Laptop"},
    )

    devices = client.get("/api/devices", headers=auth).json()

    assert [d["device_name"] for d in devices] == ["My Laptop"]
    assert devices[0]["revoked"] is False


def test_renaming_a_device(client, account, auth):
    code = client.post("/api/devices/pairing-codes", headers=auth).json()["code"]
    pair_device(client, code, name="Old")

    response = client.patch(
        "/api/devices/inst_abc", headers=auth, json={"device_name": "New name"}
    )

    assert response.status_code == 200
    assert response.json()["device_name"] == "New name"


def test_revoking_a_device_stops_its_session_at_once(client, account, auth):
    code = client.post("/api/devices/pairing-codes", headers=auth).json()["code"]
    token = client.post(
        "/api/devices/pair", json={"code": code, "device_id": "inst_abc", "device_name": "Laptop"}
    ).json()["token"]
    device_auth = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/accounts/me", headers=device_auth).status_code == 200

    revoked = client.post("/api/devices/inst_abc/revoke", headers=auth)

    assert revoked.status_code == 200
    assert revoked.json()["revoked"] is True
    assert client.get("/api/accounts/me", headers=device_auth).status_code == 401


def test_revoking_leaves_the_owner_signed_in(client, account, auth):
    code = client.post("/api/devices/pairing-codes", headers=auth).json()["code"]
    pair_device(client, code)
    client.post("/api/devices/inst_abc/revoke", headers=auth)

    assert client.get("/api/accounts/me", headers=auth).status_code == 200


def test_one_account_cannot_touch_another_accounts_device(client, account, auth):
    code = client.post("/api/devices/pairing-codes", headers=auth).json()["code"]
    pair_device(client, code)

    intruder = client.post(
        "/api/accounts/sign-up", json={"email": "other@example.com", "password": PASSWORD}
    ).json()
    intruder_auth = {"Authorization": f"Bearer {intruder['token']}"}

    assert client.post("/api/devices/inst_abc/revoke", headers=intruder_auth).status_code == 404
    assert client.patch(
        "/api/devices/inst_abc", headers=intruder_auth, json={"device_name": "Mine now"}
    ).status_code == 404
    assert client.get("/api/devices", headers=intruder_auth).json() == []


def test_a_device_already_on_another_account_is_not_moved_silently(client, account, auth):
    code = client.post("/api/devices/pairing-codes", headers=auth).json()["code"]
    pair_device(client, code)

    other = client.post(
        "/api/accounts/sign-up", json={"email": "other@example.com", "password": PASSWORD}
    ).json()
    other_code = client.post(
        "/api/devices/pairing-codes", headers={"Authorization": f"Bearer {other['token']}"}
    ).json()["code"]

    response = client.post(
        "/api/devices/pair",
        json={"code": other_code, "device_id": "inst_abc", "device_name": "L"},
    )
    assert response.status_code == 403


# --- the record -------------------------------------------------------------------------------


def test_activity_records_what_happened(client, account, auth):
    client.post("/api/accounts/sign-in", json={"email": "owner@example.com", "password": PASSWORD})

    events = client.get("/api/accounts/activity", headers=auth).json()

    assert {"sign_up", "sign_in"} <= {e["event_type"] for e in events}


def test_a_failed_sign_in_is_recorded_even_though_the_request_failed(client, account, auth):
    """The whole point of this record is that it survives the request that produced it."""
    client.post(
        "/api/accounts/sign-in", json={"email": "owner@example.com", "password": "wrong" * 3}
    )

    events = client.get("/api/accounts/activity", headers=auth).json()

    assert "sign_in_failed" in {e["event_type"] for e in events}


def test_a_failed_request_leaves_nothing_else_behind(client, account, auth):
    """Committing on a refusal must not let a half-finished change through with it."""
    before = client.get("/api/accounts/me", headers=auth).json()
    client.post(
        "/api/accounts/change-password",
        headers=auth,
        json={"current_password": "not it at all", "new_password": "a different long password"},
    )

    # The password did not change, and the session that asked is still the live one.
    assert client.get("/api/accounts/me", headers=auth).json() == before
    assert client.post(
        "/api/accounts/sign-in", json={"email": "owner@example.com", "password": PASSWORD}
    ).status_code == 200


def test_activity_is_scoped_to_the_caller(client, account, auth):
    other = client.post(
        "/api/accounts/sign-up", json={"email": "other@example.com", "password": PASSWORD}
    ).json()
    events = client.get(
        "/api/accounts/activity", headers={"Authorization": f"Bearer {other['token']}"}
    ).json()

    assert {e["event_type"] for e in events} == {"sign_up"}


def test_activity_needs_a_signed_in_caller(client):
    assert client.get("/api/accounts/activity").status_code == 401


def test_health_is_open(client):
    assert client.get("/healthz").status_code == 200
