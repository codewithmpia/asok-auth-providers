from __future__ import annotations

from unittest.mock import patch

import pytest

from asok.auth import AuthError, OAuth
from asok.core import Asok

from asok_auth_providers import (
    EXTRA_PROVIDERS,
    PROVIDER_LABELS,
    AsokAuthProvidersExtension,
    complete_oauth_flow,
    pop_next_url,
    register_extra_providers,
    start_oauth_flow,
)
from asok_auth_providers.flow import NEXT_SESSION_KEY, STATE_SESSION_KEY


# ── Fakes ──────────────────────────────────────────────────


class FakeSession(dict):
    """Minimal session object used to round-trip state."""


class FakeRequest:
    def __init__(self, app, args=None, session=None):
        self.environ = {"asok.app": app, "wsgi.url_scheme": "https", "HTTP_HOST": "example.com"}
        self.args = args or {}
        self.session = session if session is not None else FakeSession()
        self._flashes = []

    def flash(self, category, message):
        self._flashes.append((category, message))


# ── Provider registry ─────────────────────────────────────


def test_register_extra_providers_is_idempotent():
    register_extra_providers()
    before = dict(OAuth.PROVIDERS)
    register_extra_providers()
    assert OAuth.PROVIDERS == before


def test_extra_providers_are_registered():
    register_extra_providers()
    for name in ("microsoft", "discord", "facebook", "gitlab", "linkedin", "apple", "twitch"):
        assert name in OAuth.PROVIDERS, f"missing provider: {name}"
        cfg = OAuth.PROVIDERS[name]
        assert cfg["auth_url"].startswith("https://")
        assert cfg["token_url"].startswith("https://")


def test_provider_labels_cover_every_extra_provider():
    for name in EXTRA_PROVIDERS:
        assert name in PROVIDER_LABELS


# ── Extension wiring ──────────────────────────────────────


def test_extension_registration_exposes_shared_helpers():
    app = Asok()
    AsokAuthProvidersExtension(app)
    assert "oauth_providers" in app._shared
    assert "oauth_login_url" in app._shared
    # The shared providers map matches PROVIDER_LABELS.
    assert app._shared["oauth_providers"](None) is PROVIDER_LABELS
    # Helper builds the right URL.
    helper = app._shared["oauth_login_url"](None)
    assert helper("google") == "/auth/google/login"
    assert helper("github", next_url="/dashboard") == "/auth/github/login?next=%2Fdashboard"


def test_extension_stashes_self_on_app():
    app = Asok()
    ext = AsokAuthProvidersExtension(app)
    assert app._auth_providers_ext is ext


def test_extension_path_hooks_point_to_existing_directories():
    import os

    app = Asok()
    ext = AsokAuthProvidersExtension(app)
    assert os.path.isdir(ext.get_pages_path())
    assert os.path.isdir(ext.get_templates_path())
    assert os.path.isdir(ext.get_static_path())
    # Dynamic [provider] folder must be present.
    assert os.path.isdir(os.path.join(ext.get_pages_path(), "auth", "[provider]"))


# ── Flow: start_oauth_flow ────────────────────────────────


def test_start_oauth_flow_unknown_provider_raises():
    app = Asok()
    AsokAuthProvidersExtension(app)
    request = FakeRequest(app)
    with pytest.raises(AuthError, match="Unknown OAuth provider"):
        start_oauth_flow(request, "nope")


def test_start_oauth_flow_missing_config_raises():
    app = Asok()
    AsokAuthProvidersExtension(app)
    request = FakeRequest(app)
    with pytest.raises(AuthError, match="is not configured"):
        start_oauth_flow(request, "google")


def test_start_oauth_flow_missing_secret_raises():
    app = Asok()
    AsokAuthProvidersExtension(app)
    app.config["OAUTH_PROVIDERS"] = {"google": {"client_id": "abc"}}
    request = FakeRequest(app)
    with pytest.raises(AuthError, match="missing client_id"):
        start_oauth_flow(request, "google")


def test_start_oauth_flow_stores_state_and_builds_url():
    app = Asok()
    AsokAuthProvidersExtension(app)
    app.config["OAUTH_PROVIDERS"] = {
        "github": {"client_id": "id123", "client_secret": "secret"},
    }
    request = FakeRequest(app)

    url = start_oauth_flow(request, "github", next_url="/dashboard")

    # State is stashed in the session.
    state = request.session[STATE_SESSION_KEY]
    assert state and len(state) >= 32
    assert request.session[NEXT_SESSION_KEY] == "/dashboard"

    # URL targets the provider's auth endpoint and round-trips state +
    # callback URL.
    assert url.startswith("https://github.com/login/oauth/authorize?")
    assert f"state={state}" in url
    assert "redirect_uri=https%3A%2F%2Fexample.com%2Fauth%2Fgithub%2Fcallback" in url


def test_start_oauth_flow_respects_app_url_config():
    app = Asok()
    AsokAuthProvidersExtension(app)
    app.config["APP_URL"] = "https://prod.example.org/"
    app.config["OAUTH_PROVIDERS"] = {
        "github": {"client_id": "id", "client_secret": "secret"},
    }
    request = FakeRequest(app)
    url = start_oauth_flow(request, "github")
    assert "redirect_uri=https%3A%2F%2Fprod.example.org%2Fauth%2Fgithub%2Fcallback" in url


# ── Flow: complete_oauth_flow ─────────────────────────────


def test_complete_oauth_flow_missing_code_raises():
    app = Asok()
    AsokAuthProvidersExtension(app)
    app.config["OAUTH_PROVIDERS"] = {
        "github": {"client_id": "id", "client_secret": "secret"},
    }
    session = FakeSession({STATE_SESSION_KEY: "abc"})
    request = FakeRequest(app, args={"state": "abc"}, session=session)
    with pytest.raises(AuthError, match="Missing authorization code"):
        complete_oauth_flow(request, "github")


def test_complete_oauth_flow_rejects_state_mismatch():
    app = Asok()
    AsokAuthProvidersExtension(app)
    app.config["OAUTH_PROVIDERS"] = {
        "github": {"client_id": "id", "client_secret": "secret"},
    }
    session = FakeSession({STATE_SESSION_KEY: "expected"})
    request = FakeRequest(
        app,
        args={"code": "auth-code", "state": "tampered"},
        session=session,
    )
    # State mismatch surfaces as AuthError from the underlying OAuth.callback.
    with pytest.raises(AuthError, match="state validation failed"):
        complete_oauth_flow(request, "github")


def test_complete_oauth_flow_consumes_state_from_session():
    """The state must be popped — replay of the same callback URL must fail."""
    app = Asok()
    AsokAuthProvidersExtension(app)
    app.config["OAUTH_PROVIDERS"] = {
        "github": {"client_id": "id", "client_secret": "secret"},
    }
    session = FakeSession({STATE_SESSION_KEY: "stored"})
    request = FakeRequest(
        app,
        args={"code": "c", "state": "stored"},
        session=session,
    )

    with patch("asok_auth_providers.providers.OAuth._exchange_code", return_value="tok"), \
         patch(
             "asok_auth_providers.providers.OAuth._fetch_user_info",
             return_value={"provider": "github", "provider_id": "1", "email": "u@x", "name": "u", "picture": None, "raw": {}},
         ):
        complete_oauth_flow(request, "github")

    # State is gone — replay attempt now fails.
    assert STATE_SESSION_KEY not in session


# ── Apple-specific callback ───────────────────────────────


def test_apple_callback_decodes_id_token_jwt():
    """Apple identity comes from the id_token JWT, not /userinfo."""
    import base64
    import json
    from asok_auth_providers.providers import _apple_callback

    payload = {"sub": "001234.abcdef", "email": "apple.user@example.com"}
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    fake_id_token = f"header.{encoded}.signature"

    class _FakeResp:
        def __init__(self, body):
            self._body = body
        def read(self, n=None):
            return self._body
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    fake_response = _FakeResp(json.dumps({"id_token": fake_id_token}).encode())

    with patch("asok_auth_providers.providers.urllib.request.urlopen", return_value=fake_response):
        result = _apple_callback(
            client_id="cid",
            client_secret="csecret",
            code="auth-code",
            redirect_uri="https://example.com/auth/apple/callback",
            state="abc",
            expected_state="abc",
        )

    assert result["provider"] == "apple"
    assert result["provider_id"] == "001234.abcdef"
    assert result["email"] == "apple.user@example.com"


def test_apple_callback_rejects_state_mismatch():
    from asok_auth_providers.providers import _apple_callback

    with pytest.raises(AuthError, match="state validation failed"):
        _apple_callback(
            client_id="cid",
            client_secret="csecret",
            code="c",
            redirect_uri="https://example.com/auth/apple/callback",
            state="x",
            expected_state="y",
        )


def test_open_redirect_protection():
    app = Asok()
    AsokAuthProvidersExtension(app)
    app.config["OAUTH_PROVIDERS"] = {
        "github": {"client_id": "id", "client_secret": "secret"},
    }

    # 1. start_oauth_flow should ignore unsafe next URL
    request = FakeRequest(app)
    request._is_safe_redirect = lambda url: url.startswith("/") and not url.startswith("//")

    start_oauth_flow(request, "github", next_url="https://evil.com/phish")
    assert request.session.get(NEXT_SESSION_KEY) is None

    start_oauth_flow(request, "github", next_url="/dashboard")
    assert request.session.get(NEXT_SESSION_KEY) == "/dashboard"

    # 2. pop_next_url should sanitize or ignore unsafe URLs if loaded from session
    request.session[NEXT_SESSION_KEY] = "https://evil.com/phish"
    assert pop_next_url(request, default="/home") == "/home"

    request.session[NEXT_SESSION_KEY] = "/dashboard"
    assert pop_next_url(request, default="/home") == "/dashboard"


def test_template_rendering_with_custom_labels():
    from asok.templates import render_template_string
    import os

    # Load buttons.html content
    template_path = os.path.join(
        os.path.dirname(__file__),
        "../asok_auth_providers/templates/auth_providers/buttons.html"
    )
    with open(template_path, "r", encoding="utf-8") as f:
        template_content = f.read()

    # Mock helpers
    oauth_providers = {
        "google": "Google",
        "github": "GitHub",
    }

    def oauth_icon(provider):
        return f"[{provider}-icon]"

    context = {
        "providers": ["google", "github"],
        "oauth_providers": oauth_providers,
        "oauth_icon": oauth_icon,
        "labels": {"google": "Google Workspace"},
        "label_format": "Se connecter avec {}",
    }

    rendered = render_template_string(template_content, context)

    # Verify customized labels are rendered correctly
    assert "Se connecter avec Google Workspace" in rendered
    assert "Se connecter avec GitHub" in rendered


def test_template_rendering_with_extension_and_config_customizations():
    from asok.templates import render_template_string
    import os

    template_path = os.path.join(
        os.path.dirname(__file__),
        "../asok_auth_providers/templates/auth_providers/buttons.html"
    )
    with open(template_path, "r", encoding="utf-8") as f:
        template_content = f.read()

    # Mock Request class structure
    class MockApp:
        def __init__(self):
            self.config = {
                "OAUTH_PROVIDERS": {
                    "google": {"client_id": "g1", "client_secret": "gs", "label": "Google Workspace"},
                    "github": {"client_id": "h1", "client_secret": "hs"},
                }
            }

    class MockRequest:
        def __init__(self):
            self.environ = {
                "asok.app": MockApp()
            }

    def oauth_icon(provider):
        return f"[{provider}-icon]"

    oauth_providers = {
        "google": "Google",
        "github": "GitHub",
    }

    context = {
        "request": MockRequest(),
        "oauth_providers": oauth_providers,
        "oauth_icon": oauth_icon,
        "oauth_compact": True,
        "oauth_label_format": "Se connecter via {}",
    }

    rendered = render_template_string(template_content, context)

    # 1. Custom config label for google should resolve to "Google Workspace" and use format "Se connecter via Google Workspace"
    assert "Se connecter via Google Workspace" in rendered
    # 2. github should resolve to capitalized "GitHub" and use format "Se connecter via GitHub"
    assert "Se connecter via GitHub" in rendered
    # 3. oauth_compact=True should make the buttons render with compact styling (oauth-btn-compact and oauth-btn-label-hidden classes)
    assert "oauth-btn-compact" in rendered
    assert "oauth-btn-label-hidden" in rendered




