"""Signing in with Google, Apple or Facebook.

Three decisions worth stating, because each one is a place this could be got wrong quietly.

**Authorization code with PKCE, never implicit.** The code that comes back on the redirect is
worth nothing without the verifier, which never leaves this server. That matters even for a
confidential client: it closes the window where an authorization code intercepted on the
redirect (a malicious app registered for the same scheme, a shared browser) could be
exchanged by someone else.

**`state` is stored, not signed into the URL.** Each flow gets a row here that is looked up,
spent, and expires in minutes. A callback carrying a `state` we did not issue is someone
else's request arriving at our door, and it is refused rather than followed.

**Linking to an existing account needs a *verified* address from the provider.** If someone
signs up with `you@example.com` at a provider that never checked they can read that inbox, and
we linked on the address alone, they would land inside the existing account. So an unverified
address never links; it makes its own account.

Providers are configured by environment variable and simply absent when they are not. The
routes offer what is configured and refuse the rest, so a half-set-up provider cannot appear
as a working button.
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

PKCE_METHOD = "S256"

# A flow is a person clicking through a consent screen. Minutes, not hours.
FLOW_LIFETIME_MINUTES = 10

# The window between the provider redirecting back and the website exchanging the handoff.
# It is one automatic request, so it can be very short.
HANDOFF_LIFETIME_SECONDS = 120


@dataclass(frozen=True, slots=True)
class Provider:
    """One identity provider, and where to talk to it."""

    name: str
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    userinfo_url: str
    scope: str

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)


def _provider(name: str, authorize: str, token: str, userinfo: str, scope: str) -> Provider:
    prefix = f"MYAI_OAUTH_{name.upper()}"
    return Provider(
        name=name,
        client_id=os.getenv(f"{prefix}_CLIENT_ID", ""),
        client_secret=os.getenv(f"{prefix}_CLIENT_SECRET", ""),
        # The endpoints are overridable so a test can point a whole flow at a local fake
        # without any of this code knowing it is being tested.
        authorize_url=os.getenv(f"{prefix}_AUTHORIZE_URL", authorize),
        token_url=os.getenv(f"{prefix}_TOKEN_URL", token),
        userinfo_url=os.getenv(f"{prefix}_USERINFO_URL", userinfo),
        scope=os.getenv(f"{prefix}_SCOPE", scope),
    )


def providers() -> dict[str, Provider]:
    """Every provider this build knows about, configured or not."""
    return {
        "google": _provider(
            "google",
            "https://accounts.google.com/o/oauth2/v2/auth",
            "https://oauth2.googleapis.com/token",
            "https://openidconnect.googleapis.com/v1/userinfo",
            "openid email profile",
        ),
        "apple": _provider(
            "apple",
            "https://appleid.apple.com/auth/authorize",
            "https://appleid.apple.com/auth/token",
            # Apple returns identity in the token response rather than from a userinfo
            # endpoint; `identity.py` handles that difference.
            "",
            "name email",
        ),
        "facebook": _provider(
            "facebook",
            "https://www.facebook.com/v21.0/dialog/oauth",
            "https://graph.facebook.com/v21.0/oauth/access_token",
            "https://graph.facebook.com/me?fields=id,name,email",
            "email",
        ),
    }


def configured_providers() -> dict[str, Provider]:
    return {name: p for name, p in providers().items() if p.configured}


def new_state() -> str:
    return secrets.token_urlsafe(32)


def new_verifier() -> str:
    """A PKCE code verifier: 43-128 characters from the unreserved set (RFC 7636 §4.1)."""
    return secrets.token_urlsafe(64)


def challenge_for(verifier: str) -> str:
    """S256 challenge: base64url(sha256(verifier)), unpadded (RFC 7636 §4.2)."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def authorization_url(provider: Provider, *, state: str, verifier: str, redirect_uri: str) -> str:
    query: dict[str, Any] = {
        "client_id": provider.client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": provider.scope,
        "state": state,
        "code_challenge": challenge_for(verifier),
        "code_challenge_method": PKCE_METHOD,
    }
    if provider.name == "apple":
        # Apple only returns the address with form_post, and only on the first consent.
        query["response_mode"] = "form_post"
    return f"{provider.authorize_url}?{urlencode(query)}"
