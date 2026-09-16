"""Signing in with a provider: start, come back, hand over.

All four routes are unauthenticated by necessity — someone signing in has no session yet —
so the protection is in the flow rather than in a credential: `state` must be one this server
issued and has not spent, the PKCE verifier never leaves this server, and the handoff is
single use and lives for two minutes.

The redirect back to the website is always built from the configured `base_url`. It never
takes a destination from the request, because a callback that forwards wherever it is told is
an open redirect, and an open redirect on a sign-in route is a phishing tool.
"""

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from myai_server import identity as identity_module
from myai_server import oauth
from myai_server.deps import ServiceDep, StateDep
from myai_server.schemas import ApiModel, AuthResult, account_read

router = APIRouter(prefix="/oauth", tags=["oauth"])


class ProviderRead(ApiModel):
    name: str
    label: str


class HandoffRequest(ApiModel):
    handoff: str


LABELS = {"google": "Google", "apple": "Apple", "facebook": "Facebook"}


def _provider_or_404(name: str) -> oauth.Provider:
    provider = oauth.configured_providers().get(name)
    if provider is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Signing in with {LABELS.get(name, name)} is not set up on this server.",
        )
    return provider


def _redirect_uri(request: Request, name: str) -> str:
    """The callback address, as the provider must be told and later shown again.

    Built from the request's own base so a deployment does not need it configured twice, and
    it has to match byte for byte between the authorize call and the token exchange.
    """
    return str(request.url_for("oauth_callback", provider=name))


def _back_to_site(state: StateDep, **params: str) -> RedirectResponse:
    base = state.settings.base_url.rstrip("/")
    return RedirectResponse(f"{base}/oauth/finish?{urlencode(params)}", status_code=303)


@router.get("/providers", response_model=list[ProviderRead])
def list_providers() -> list[ProviderRead]:
    """Which providers this server can actually use, so the website offers only those."""
    return [
        ProviderRead(name=name, label=LABELS.get(name, name.title()))
        for name in oauth.configured_providers()
    ]


@router.get("/{provider}/start")
def start(provider: str, request: Request, service: ServiceDep) -> RedirectResponse:
    """Begin a sign-in: record the flow, then send the browser to the provider."""
    chosen = _provider_or_404(provider)
    redirect_uri = _redirect_uri(request, provider)
    state, verifier = service.start_oauth_flow(provider, redirect_uri)
    return RedirectResponse(
        oauth.authorization_url(chosen, state=state, verifier=verifier, redirect_uri=redirect_uri),
        status_code=307,
    )


@router.api_route("/{provider}/callback", methods=["GET", "POST"], name="oauth_callback")
async def callback(
    provider: str, request: Request, service: ServiceDep, state: StateDep
) -> RedirectResponse:
    """Where the provider sends the browser back.

    POST as well as GET because Apple uses `response_mode=form_post`; everything after
    reading the two parameters is identical.

    Every failure lands back on the website with a reason rather than showing a bare error
    here — the person is mid-sign-in in their browser, not reading an API response.
    """
    chosen = _provider_or_404(provider)
    params = dict(request.query_params)
    if request.method == "POST":
        params.update(dict(await request.form()))

    if params.get("error"):
        return _back_to_site(state, error="You cancelled, or the provider refused.")

    code, returned_state = params.get("code"), params.get("state")
    if not code or not returned_state:
        return _back_to_site(state, error="That sign-in came back incomplete.")

    flow = service.take_oauth_flow(returned_state)
    if flow is None or flow.provider != provider:
        return _back_to_site(
            state, error="That sign-in link has expired or was already used. Try again."
        )

    try:
        tokens = await identity_module.exchange_code(
            chosen, code=code, verifier=flow.code_verifier, redirect_uri=flow.redirect_uri
        )
        who = await identity_module.fetch_identity(chosen, tokens)
    except identity_module.IdentityError as exc:
        return _back_to_site(state, error=str(exc))

    account, refusal = service.resolve_oauth_account(
        provider, who.subject, who.email, who.email_verified
    )
    if account is None:
        return _back_to_site(state, error=refusal or "That account could not be used.")

    handoff = service.issue_handoff(flow, account.account_id)
    return _back_to_site(state, handoff=handoff)


@router.post("/handoff", response_model=AuthResult)
def redeem(body: HandoffRequest, service: ServiceDep) -> AuthResult:
    """Swap the handoff from the redirect for a real session.

    The session token is returned here, in a response body, rather than in the redirect —
    a URL ends up in history and in any referrer, and this one does not have to.
    """
    result = service.redeem_handoff(body.handoff)
    if result is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "That sign-in has expired. Please try again."
        )
    account, token = result
    return AuthResult(token=token, account=account_read(account))
