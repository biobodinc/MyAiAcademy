"""Signing in with a provider.

The HTTP calls out to Google, Apple and Facebook are thin wrappers over httpx and are
stubbed here; what is tested is everything around them, which is where this can go wrong
without anybody noticing: whether `state` is really single use, whether PKCE is computed the
way RFC 7636 says, and — most of all — the rules about when a provider identity is allowed to
join an account that already exists.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
from datetime import UTC, datetime, timedelta

import pytest

from myai_server import identity as identity_module
from myai_server import oauth
from myai_server.identity import Identity, IdentityError
from myai_server.models import OAuthFlow
from myai_server.services import AccountService

from .conftest import PASSWORD

# --- PKCE ---------------------------------------------------------------------------------


def test_the_challenge_is_base64url_sha256_of_the_verifier():
    """RFC 7636 §4.2: BASE64URL-ENCODE(SHA256(ASCII(verifier))), with padding stripped."""
    verifier = oauth.new_verifier()
    expected = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
        .decode("ascii")
        .rstrip("=")
    )
    assert oauth.challenge_for(verifier) == expected


def test_the_verifier_is_within_the_length_the_spec_allows():
    assert 43 <= len(oauth.new_verifier()) <= 128


def test_two_flows_never_share_a_verifier():
    assert oauth.new_verifier() != oauth.new_verifier()


def test_the_authorization_url_carries_the_challenge_and_not_the_verifier():
    provider = oauth.Provider(
        name="google",
        client_id="cid",
        client_secret="secret",
        authorize_url="https://provider.example/auth",
        token_url="https://provider.example/token",
        userinfo_url="https://provider.example/me",
        scope="openid email",
    )
    verifier = oauth.new_verifier()
    url = oauth.authorization_url(
        provider, state="st", verifier=verifier, redirect_uri="https://api.example/cb"
    )

    assert oauth.challenge_for(verifier) in url
    assert "code_challenge_method=S256" in url
    assert verifier not in url, "the verifier must never leave this server"
    assert "secret" not in url


# --- the flow record ----------------------------------------------------------------------


def test_a_flow_can_only_be_spent_once(in_memory_db):
    service = AccountService(in_memory_db)
    state, _ = service.start_oauth_flow("google", "https://api.example/cb")

    assert service.take_oauth_flow(state) is not None
    assert service.take_oauth_flow(state) is None


def test_a_state_we_never_issued_is_refused(in_memory_db):
    assert AccountService(in_memory_db).take_oauth_flow("not-ours") is None


def test_an_expired_flow_is_refused(in_memory_db):
    service = AccountService(in_memory_db)
    state, _ = service.start_oauth_flow("google", "https://api.example/cb")
    flow = in_memory_db.query(OAuthFlow).filter_by(state=state).one()
    flow.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    in_memory_db.flush()

    assert service.take_oauth_flow(state) is None


# --- who the account belongs to -----------------------------------------------------------


def test_the_same_provider_identity_returns_the_same_account(in_memory_db):
    service = AccountService(in_memory_db)
    first, _ = service.resolve_oauth_account("google", "sub-1", "a@example.com", True)
    second, _ = service.resolve_oauth_account("google", "sub-1", "a@example.com", True)

    assert first is not None and second is not None
    assert first.account_id == second.account_id


def test_an_account_is_keyed_on_the_subject_not_the_address(in_memory_db):
    """A provider address can change, and at some providers be reassigned to someone else."""
    service = AccountService(in_memory_db)
    original, _ = service.resolve_oauth_account("google", "sub-1", "old@example.com", True)
    later, _ = service.resolve_oauth_account("google", "sub-1", "new@example.com", True)

    assert later is not None and original is not None
    assert later.account_id == original.account_id


def test_a_verified_address_joins_the_password_account_that_already_has_it(in_memory_db):
    service = AccountService(in_memory_db)
    existing, _ = service.sign_up("owner@example.com", PASSWORD)
    in_memory_db.flush()

    linked, refusal = service.resolve_oauth_account("google", "sub-1", "owner@example.com", True)

    assert refusal is None
    assert linked is not None and linked.account_id == existing.account_id
    assert linked.oauth_provider == "google"
    assert linked.email_verified_at is not None


def test_an_unverified_address_never_joins_an_existing_account(in_memory_db):
    """Otherwise anyone who typed your address into a provider profile walks into your account."""
    service = AccountService(in_memory_db)
    existing, _ = service.sign_up("owner@example.com", PASSWORD)
    in_memory_db.flush()

    intruder, _ = service.resolve_oauth_account("google", "sub-evil", "owner@example.com", False)

    assert intruder is not None
    assert intruder.account_id != existing.account_id
    assert existing.oauth_provider is None


def test_an_unverified_address_is_not_stored_at_all(in_memory_db):
    """The address column is unique, so keeping it would let an identity squat an address."""
    service = AccountService(in_memory_db)
    account, _ = service.resolve_oauth_account("google", "sub-1", "someone@example.com", False)

    assert account is not None
    assert account.email is None


def test_an_address_already_linked_to_another_provider_is_refused(in_memory_db):
    service = AccountService(in_memory_db)
    service.resolve_oauth_account("google", "sub-google", "owner@example.com", True)
    in_memory_db.flush()

    account, refusal = service.resolve_oauth_account(
        "facebook", "sub-facebook", "owner@example.com", True
    )

    assert account is None
    assert refusal is not None and "Google" in refusal


# --- the handoff --------------------------------------------------------------------------


def test_a_handoff_becomes_a_session_exactly_once(in_memory_db):
    service = AccountService(in_memory_db)
    state, _ = service.start_oauth_flow("google", "https://api.example/cb")
    flow = service.take_oauth_flow(state)
    account, _ = service.resolve_oauth_account("google", "sub-1", "a@example.com", True)
    assert flow is not None and account is not None

    handoff = service.issue_handoff(flow, account.account_id)

    first = service.redeem_handoff(handoff)
    assert first is not None
    signed_in, token = first
    assert signed_in.account_id == account.account_id
    assert service.authenticate(token) is not None

    assert service.redeem_handoff(handoff) is None, "a handoff in browser history is worth nothing"


def test_an_expired_handoff_is_refused(in_memory_db):
    service = AccountService(in_memory_db)
    state, _ = service.start_oauth_flow("google", "https://api.example/cb")
    flow = service.take_oauth_flow(state)
    account, _ = service.resolve_oauth_account("google", "sub-1", "a@example.com", True)
    assert flow is not None and account is not None

    handoff = service.issue_handoff(flow, account.account_id)
    flow.handoff_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    in_memory_db.flush()

    assert service.redeem_handoff(handoff) is None


def test_a_made_up_handoff_is_refused(in_memory_db):
    assert AccountService(in_memory_db).redeem_handoff("invented") is None


# --- reading what a provider said ---------------------------------------------------------


def _jwt(claims: dict) -> str:
    def seg(data: dict) -> str:
        import json

        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")

    return f"{seg({'alg': 'RS256'})}.{seg(claims)}.signature-not-checked"


def test_apple_identity_comes_from_the_id_token():
    apple = oauth.providers()["apple"]
    claims = {"sub": "apple-1", "email": "a@example.com", "email_verified": "true"}
    who = asyncio.run(identity_module.fetch_identity(apple, {"id_token": _jwt(claims)}))

    assert who.subject == "apple-1"
    assert who.email == "a@example.com"
    assert who.email_verified is True


def test_apple_without_an_id_token_is_an_error():
    with pytest.raises(IdentityError):
        asyncio.run(
            identity_module.fetch_identity(oauth.providers()["apple"], {"access_token": "x"})
        )


def test_a_malformed_identity_token_is_refused():
    with pytest.raises(IdentityError):
        identity_module.decode_jwt_payload("not.a.jwt")


def test_an_identity_with_no_subject_is_refused():
    with pytest.raises(IdentityError):
        identity_module._identity(
            subject=None, email="a@example.com", email_verified=True, name=None
        )


def test_addresses_are_normalised():
    who = identity_module._identity(
        subject="s", email="  Mixed@Example.COM ", email_verified=True, name="  "
    )
    assert who.email == "mixed@example.com"
    assert who.name is None


def test_identity_is_what_the_routes_receive():
    """A guard on the shape the rest of the code relies on."""
    who = Identity(subject="s", email=None, email_verified=False, name=None)
    assert who.subject == "s"


# --- the routes ---------------------------------------------------------------------------


@pytest.fixture
def google(monkeypatch):
    """A configured provider, with the calls out to it stubbed."""
    monkeypatch.setenv("MYAI_OAUTH_GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("MYAI_OAUTH_GOOGLE_CLIENT_SECRET", "secret")

    async def fake_exchange(provider, **kwargs):
        return {"access_token": "at"}

    async def fake_identity(provider, tokens):
        return Identity(
            subject="sub-1", email="person@example.com", email_verified=True, name="Person"
        )

    monkeypatch.setattr(identity_module, "exchange_code", fake_exchange)
    monkeypatch.setattr(identity_module, "fetch_identity", fake_identity)


def _start(client) -> str:
    """Begin a flow and return the `state` the server issued."""
    response = client.get("/api/oauth/google/start", follow_redirects=False)
    assert response.status_code == 307
    location = response.headers["location"]
    return dict(param.split("=", 1) for param in location.split("?", 1)[1].split("&"))["state"]


def test_only_configured_providers_are_offered(client, google):
    assert client.get("/api/oauth/providers").json() == [{"name": "google", "label": "Google"}]


def test_an_unconfigured_provider_is_not_startable(client):
    assert client.get("/api/oauth/facebook/start", follow_redirects=False).status_code == 404


def test_the_callback_accepts_a_form_post(client, google):
    """Apple uses `response_mode=form_post`, so the callback must read a form body."""
    state = _start(client)

    response = client.post(
        "/api/oauth/google/callback",
        data={"code": "auth-code", "state": state},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "handoff=" in response.headers["location"]


def test_the_callback_accepts_a_query_string(client, google):
    state = _start(client)
    response = client.get(
        f"/api/oauth/google/callback?code=auth-code&state={state}", follow_redirects=False
    )
    assert response.status_code == 303
    assert "handoff=" in response.headers["location"]


def test_a_callback_always_returns_to_the_configured_site(client, google):
    """Never to somewhere named in the request: an open redirect on sign-in is a phishing tool."""
    state = _start(client)
    response = client.get(
        f"/api/oauth/google/callback?code=c&state={state}&redirect_uri=https://evil.example",
        follow_redirects=False,
    )
    assert response.headers["location"].startswith("https://example.com/oauth/finish")


def test_a_callback_with_an_unknown_state_comes_back_with_a_reason(client, google):
    response = client.get(
        "/api/oauth/google/callback?code=c&state=never-issued", follow_redirects=False
    )
    assert response.status_code == 303
    assert "error=" in response.headers["location"]
    assert "handoff=" not in response.headers["location"]


def test_a_replayed_callback_is_refused(client, google):
    state = _start(client)
    first = client.get(f"/api/oauth/google/callback?code=c&state={state}", follow_redirects=False)
    second = client.get(f"/api/oauth/google/callback?code=c&state={state}", follow_redirects=False)

    assert "handoff=" in first.headers["location"]
    assert "error=" in second.headers["location"]


def test_the_provider_reporting_an_error_is_passed_on_plainly(client, google):
    state = _start(client)
    response = client.get(
        f"/api/oauth/google/callback?error=access_denied&state={state}", follow_redirects=False
    )
    assert "error=" in response.headers["location"]


def test_the_handoff_from_a_real_callback_signs_you_in(client, google):
    state = _start(client)
    location = client.get(
        f"/api/oauth/google/callback?code=c&state={state}", follow_redirects=False
    ).headers["location"]
    handoff = location.split("handoff=", 1)[1]

    signed_in = client.post("/api/oauth/handoff", json={"handoff": handoff})

    assert signed_in.status_code == 200
    body = signed_in.json()
    assert body["account"]["email"] == "person@example.com"
    assert body["account"]["email_verified"] is True
    assert (
        client.get(
            "/api/accounts/me", headers={"Authorization": f"Bearer {body['token']}"}
        ).status_code
        == 200
    )


def test_a_made_up_handoff_is_refused_by_the_route(client):
    assert client.post("/api/oauth/handoff", json={"handoff": "invented"}).status_code == 403
