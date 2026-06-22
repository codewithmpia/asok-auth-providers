from __future__ import annotations

import secrets
from typing import Any, Optional

from asok.auth import AuthError, OAuth

from .providers import callback_for, register_extra_providers

# Session key used to round-trip the OAuth `state` parameter.
STATE_SESSION_KEY = "_oauth_state"
# Session key used to round-trip the post-login redirect target.
NEXT_SESSION_KEY = "_oauth_next"


def _provider_config(app: Any, provider: str) -> dict[str, str]:
    """Resolve client_id / client_secret for a given provider from app.config."""
    providers_config = app.config.get("OAUTH_PROVIDERS", {}) or {}
    cfg = providers_config.get(provider) or providers_config.get(provider.lower())
    if not cfg:
        raise AuthError(f"OAuth provider '{provider}' is not configured")
    if not cfg.get("client_id") or not cfg.get("client_secret"):
        raise AuthError(f"OAuth provider '{provider}' is missing client_id/client_secret")
    return cfg


def _build_redirect_uri(request: Any, provider: str) -> str:
    """Build the absolute callback URL for a given provider.

    Respects an explicit `APP_URL` config when set (mandatory in production
    per the framework's host-header guidance); otherwise reconstructs from
    the current request scheme + host.
    """
    app = request.environ.get("asok.app")
    app_url = app.config.get("APP_URL") if app else None
    if app_url:
        base = app_url.rstrip("/")
    else:
        scheme = request.environ.get("wsgi.url_scheme", "http")
        host = request.environ.get("HTTP_HOST") or request.environ.get("SERVER_NAME", "localhost")
        base = f"{scheme}://{host}"
    return f"{base}/auth/{provider}/callback"


def start_oauth_flow(request: Any, provider: str, next_url: Optional[str] = None) -> str:
    """Start the OAuth dance for `provider`.

    Returns the URL the user must be redirected to.
    """
    register_extra_providers()
    if provider.lower() not in OAuth.PROVIDERS:
        raise AuthError(f"Unknown OAuth provider: {provider}")

    app = request.environ.get("asok.app")
    if not app:
        raise AuthError("Application context is unavailable")

    cfg = _provider_config(app, provider)
    state = secrets.token_urlsafe(32)
    request.session[STATE_SESSION_KEY] = state
    if next_url:
        is_safe = False
        if hasattr(request, "_is_safe_redirect"):
            is_safe = request._is_safe_redirect(next_url)
        else:
            is_safe = next_url.startswith("/") and not next_url.startswith("//")
        if is_safe:
            request.session[NEXT_SESSION_KEY] = next_url

    redirect_uri = _build_redirect_uri(request, provider)
    return OAuth.get_auth_url(
        provider_name=provider,
        client_id=cfg["client_id"],
        redirect_uri=redirect_uri,
        state=state,
    )


def complete_oauth_flow(request: Any, provider: str) -> dict[str, Any]:
    """Validate the callback request and return normalized user info."""
    register_extra_providers()
    app = request.environ.get("asok.app")
    if not app:
        raise AuthError("Application context is unavailable")

    cfg = _provider_config(app, provider)
    code = request.args.get("code")
    state = request.args.get("state")
    if not code:
        raise AuthError("Missing authorization code")

    expected_state = request.session.pop(STATE_SESSION_KEY, None)
    redirect_uri = _build_redirect_uri(request, provider)
    return callback_for(
        provider=provider,
        client_id=cfg["client_id"],
        client_secret=cfg["client_secret"],
        code=code,
        redirect_uri=redirect_uri,
        state=state,
        expected_state=expected_state,
    )


def pop_next_url(request: Any, default: str = "/") -> str:
    """Pop and return the post-login redirect target, ensuring it is safe."""
    next_url = request.session.pop(NEXT_SESSION_KEY, None)
    if next_url:
        is_safe = False
        if hasattr(request, "_is_safe_redirect"):
            is_safe = request._is_safe_redirect(next_url)
        else:
            is_safe = next_url.startswith("/") and not next_url.startswith("//")
        if is_safe:
            return next_url
    return default
