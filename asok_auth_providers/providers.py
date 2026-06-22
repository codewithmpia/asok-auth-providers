from __future__ import annotations

import json
import secrets
import urllib.parse
import urllib.request
from typing import Any, Optional

from asok.auth import AuthError, OAuth


# Extra providers shipped by asok-auth-providers, in addition to the
# google/github pair already present in asok.auth.OAuth.PROVIDERS.
EXTRA_PROVIDERS: dict[str, dict[str, str]] = {
    "microsoft": {
        "auth_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "user_url": "https://graph.microsoft.com/oidc/userinfo",
        "scopes": "openid email profile",
    },
    "discord": {
        "auth_url": "https://discord.com/api/oauth2/authorize",
        "token_url": "https://discord.com/api/oauth2/token",
        "user_url": "https://discord.com/api/users/@me",
        "scopes": "identify email",
    },
    "facebook": {
        "auth_url": "https://www.facebook.com/v18.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v18.0/oauth/access_token",
        "user_url": "https://graph.facebook.com/me?fields=id,name,email,picture",
        "scopes": "email public_profile",
    },
    "gitlab": {
        "auth_url": "https://gitlab.com/oauth/authorize",
        "token_url": "https://gitlab.com/oauth/token",
        "user_url": "https://gitlab.com/api/v4/user",
        "scopes": "read_user",
    },
    "linkedin": {
        "auth_url": "https://www.linkedin.com/oauth/v2/authorization",
        "token_url": "https://www.linkedin.com/oauth/v2/accessToken",
        "user_url": "https://api.linkedin.com/v2/userinfo",
        "scopes": "openid email profile",
    },
    "apple": {
        "auth_url": "https://appleid.apple.com/auth/authorize",
        "token_url": "https://appleid.apple.com/auth/token",
        # Apple does not expose a userinfo endpoint; identity is in the id_token JWT.
        "user_url": "",
        "scopes": "name email",
    },
    "twitch": {
        "auth_url": "https://id.twitch.tv/oauth2/authorize",
        "token_url": "https://id.twitch.tv/oauth2/token",
        "user_url": "https://api.twitch.tv/helix/users",
        "scopes": "user:read:email",
    },
}


# Display labels used by the sign-in button macro.
PROVIDER_LABELS: dict[str, str] = {
    "google": "Google",
    "github": "GitHub",
    "microsoft": "Microsoft",
    "discord": "Discord",
    "facebook": "Facebook",
    "gitlab": "GitLab",
    "linkedin": "LinkedIn",
    "apple": "Apple",
    "twitch": "Twitch",
}


def register_extra_providers() -> None:
    """Merge EXTRA_PROVIDERS into asok.auth.OAuth.PROVIDERS.

    Idempotent: re-running has no effect.
    """
    for name, config in EXTRA_PROVIDERS.items():
        OAuth.PROVIDERS.setdefault(name, config)


def _decode_id_token_payload(id_token: str) -> dict[str, Any]:
    """Decode a JWT id_token payload without signature verification.

    NOTE: signature verification against Apple's public JWKS should be
    layered on top in production; this helper extracts claims only so the
    callback page can surface `sub`, `email`, and `name`.
    """
    parts = id_token.split(".")
    if len(parts) < 2:
        raise AuthError("Malformed id_token")
    payload = parts[1]
    # base64url decoding with padding fix-up
    import base64

    padding = "=" * (-len(payload) % 4)
    raw = base64.urlsafe_b64decode(payload + padding)
    return json.loads(raw.decode("utf-8"))


def _apple_callback(
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    state: str,
    expected_state: str,
) -> dict[str, Any]:
    """Apple-specific callback: exchanges the code and decodes the id_token JWT."""
    if not expected_state:
        raise AuthError("OAuth expected_state is required")
    if not state or not secrets.compare_digest(state, expected_state):
        raise AuthError("OAuth state validation failed")

    config = OAuth.PROVIDERS["apple"]
    token_data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    req = urllib.request.Request(
        config["token_url"],
        data=urllib.parse.urlencode(token_data).encode(),
        headers={"Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            response_data = response.read(100_000)
            res = json.loads(response_data.decode())
    except Exception as e:
        raise AuthError(f"Apple OAuth token request failed: {e}")

    id_token = res.get("id_token")
    if not id_token:
        raise AuthError(f"Apple OAuth token exchange failed: {res}")

    claims = _decode_id_token_payload(id_token)
    return {
        "provider": "apple",
        "provider_id": str(claims.get("sub")),
        "email": claims.get("email"),
        "name": claims.get("name"),
        "picture": None,
        "raw": claims,
    }


def callback_for(
    provider: str,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    state: Optional[str],
    expected_state: Optional[str],
) -> dict[str, Any]:
    """Dispatch the callback to the right handler.

    Falls back to the generic asok.auth.OAuth.callback flow for every provider
    except Apple, which requires JWT-based identity extraction.
    """
    register_extra_providers()
    if provider.lower() == "apple":
        return _apple_callback(
            client_id,
            client_secret,
            code,
            redirect_uri,
            state or "",
            expected_state or "",
        )
    return OAuth.callback(
        provider_name=provider,
        client_id=client_id,
        client_secret=client_secret,
        code=code,
        redirect_uri=redirect_uri,
        state=state,
        expected_state=expected_state,
    )
