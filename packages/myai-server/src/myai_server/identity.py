"""Turning an authorization code into "who is this", per provider.

Each provider answers the same question differently, and the differences are the whole of
this module:

* **Google** returns an OIDC userinfo document with `sub`, `email` and `email_verified`.
* **Facebook** returns `id`, `name` and `email` from the Graph API, with no verification flag
  — Facebook only releases an address it has confirmed, so one that arrives is treated as
  verified and one that does not arrive is simply absent.
* **Apple** has no userinfo endpoint. Identity is in the `id_token` of the token response.

**Why Apple's `id_token` signature is not checked here.** It arrives in the response to a
request this server made directly to Apple's token endpoint over TLS. OpenID Connect Core
§3.1.3.7 says a client need not validate the signature when the token came through exactly
that channel, because TLS already authenticated who sent it. The exemption is narrow and
depends on the token never having passed through the browser — so if this ever moves to a
flow where the client receives an `id_token` from a redirect, the signature must be verified
against Apple's JWKS before anything here trusts a claim in it.
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from typing import Any

import httpx

from myai_server.oauth import Provider

# A provider that is slow is a sign-in that hangs. Fail and let the person try again.
TIMEOUT_SECONDS = 10.0


class IdentityError(Exception):
    """The provider did not give us a usable identity."""


@dataclass(frozen=True, slots=True)
class Identity:
    """Who the provider says this is."""

    subject: str
    """The provider's own stable id. This, not the address, is what an account is keyed on:
    an email can be changed at the provider and reassigned to somebody else."""

    email: str | None
    email_verified: bool
    name: str | None


async def exchange_code(
    provider: Provider, *, code: str, verifier: str, redirect_uri: str
) -> dict[str, Any]:
    """Swap the authorization code for tokens, proving we started the flow with the verifier."""
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        response = await client.post(
            provider.token_url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": provider.client_id,
                "client_secret": provider.client_secret,
                "code_verifier": verifier,
            },
            headers={"Accept": "application/json"},
        )
    if response.status_code != 200:
        # Deliberately not repeating the provider's body: it can echo the code and secret.
        raise IdentityError("The sign-in provider refused the exchange.")
    try:
        return response.json()
    except ValueError as exc:
        raise IdentityError("The sign-in provider sent something unreadable.") from exc


async def fetch_identity(provider: Provider, tokens: dict[str, Any]) -> Identity:
    if provider.name == "apple":
        return _from_id_token(tokens)

    access_token = tokens.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise IdentityError("The sign-in provider did not return an access token.")

    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        response = await client.get(
            provider.userinfo_url,
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        )
    if response.status_code != 200:
        raise IdentityError("The sign-in provider would not say who you are.")
    try:
        claims = response.json()
    except ValueError as exc:
        raise IdentityError("The sign-in provider sent something unreadable.") from exc

    if provider.name == "facebook":
        return _identity(
            subject=claims.get("id"),
            email=claims.get("email"),
            # Facebook does not send a flag because it does not release an unconfirmed
            # address at all. An address that arrives has been confirmed by Facebook.
            email_verified=bool(claims.get("email")),
            name=claims.get("name"),
        )

    return _identity(
        subject=claims.get("sub"),
        email=claims.get("email"),
        email_verified=bool(claims.get("email_verified")),
        name=claims.get("name"),
    )


def _from_id_token(tokens: dict[str, Any]) -> Identity:
    raw = tokens.get("id_token")
    if not isinstance(raw, str):
        raise IdentityError("The sign-in provider did not return an identity token.")
    claims = decode_jwt_payload(raw)
    return _identity(
        subject=claims.get("sub"),
        email=claims.get("email"),
        # Apple sends this as the string "true" as often as a boolean.
        email_verified=str(claims.get("email_verified", "")).lower() == "true",
        name=None,  # Apple sends a name once, in the form post, not in the token.
    )


def decode_jwt_payload(token: str) -> dict[str, Any]:
    """Read a JWT's claims without verifying it. See the module docstring for when that is
    acceptable — it is not, unless the token arrived over a direct TLS call to the issuer."""
    parts = token.split(".")
    if len(parts) != 3:
        raise IdentityError("The identity token was not a JWT.")
    padding = "=" * (-len(parts[1]) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + padding))
    except (ValueError, binascii.Error) as exc:
        raise IdentityError("The identity token could not be read.") from exc
    if not isinstance(payload, dict):
        raise IdentityError("The identity token had no claims.")
    return payload


def _identity(*, subject: Any, email: Any, email_verified: bool, name: Any) -> Identity:
    if not isinstance(subject, str) or not subject:
        raise IdentityError("The sign-in provider did not identify you.")
    return Identity(
        subject=subject,
        email=email.strip().lower() if isinstance(email, str) and email.strip() else None,
        email_verified=email_verified,
        name=name if isinstance(name, str) and name.strip() else None,
    )
