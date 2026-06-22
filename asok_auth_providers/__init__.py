from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Callable, Optional

from asok import AsokExtension

from ._icons import ICONS as PROVIDER_ICONS
from ._icons import get_icon
from .flow import (
    NEXT_SESSION_KEY,
    STATE_SESSION_KEY,
    complete_oauth_flow,
    pop_next_url,
    start_oauth_flow,
)
from .providers import (
    EXTRA_PROVIDERS,
    PROVIDER_LABELS,
    callback_for,
    register_extra_providers,
)

if TYPE_CHECKING:
    from asok.core.asok import Asok


# Type for the user-supplied login hook.
# Signature: (request, user_info_dict) -> None
LoginHook = Callable[[Any, dict[str, Any]], None]


class AsokAuthProvidersExtension(AsokExtension):
    """Drop-in OAuth providers extension for the Asok framework.

    Registers extra providers (Microsoft, Apple, Discord, Facebook, GitLab,
    LinkedIn, Twitch) on top of the google/github pair already shipped in
    asok.auth.OAuth, and mounts ready-to-use ``/auth/<provider>/login`` and
    ``/auth/<provider>/callback`` pages.

    Configuration is read from ``app.config["OAUTH_PROVIDERS"]``::

        app.config["OAUTH_PROVIDERS"] = {
            "google":    {"client_id": "...", "client_secret": "..."},
            "microsoft": {"client_id": "...", "client_secret": "..."},
        }

    The ``on_login`` callable receives the request and the normalized user
    dict and is responsible for finding/creating a local user and calling
    ``request.login(user)``.
    """

    def __init__(
        self,
        app: Optional[Asok] = None,
        on_login: Optional[LoginHook] = None,
        login_redirect: str = "/",
        login_failed_redirect: str = "/login",
        compact: bool = False,
        label_format: str = "",
    ) -> None:
        self.on_login: Optional[LoginHook] = on_login
        self.login_redirect = login_redirect
        self.login_failed_redirect = login_failed_redirect
        self.compact = compact
        self.label_format = label_format
        super().__init__(app)

    # ── Lifecycle ───────────────────────────────────────────

    def init_app(self, app: Asok) -> None:
        super().init_app(app)

        # 1. Merge extra providers into the global OAuth registry.
        register_extra_providers()

        # 2. Stash the extension instance on the app so page handlers can
        #    look it up via request.environ["asok.app"]._auth_providers_ext.
        app._auth_providers_ext = self  # type: ignore[attr-defined]

        # 3. Expose helpers in templates.
        app.share(oauth_providers=lambda request: PROVIDER_LABELS)
        app.share(oauth_login_url=lambda request: _login_url_factory)
        app.share(oauth_providers_css=lambda request: _css_loader)
        app.share(oauth_icon=lambda request: _icon_helper)
        app.share(oauth_compact=lambda request: self.compact)
        app.share(oauth_label_format=lambda request: self.label_format)

    # ── Path hooks ──────────────────────────────────────────

    def get_pages_path(self) -> Optional[str]:
        return os.path.join(os.path.dirname(__file__), "pages")

    def get_templates_path(self) -> Optional[str]:
        return os.path.join(os.path.dirname(__file__), "templates")

    def get_static_path(self) -> Optional[str]:
        return os.path.join(os.path.dirname(__file__), "static")


def _login_url_factory(provider: str, next_url: Optional[str] = None) -> str:
    """Template helper: build a `/auth/<provider>/login` URL with an optional next."""
    base = f"/auth/{provider}/login"
    if next_url:
        from urllib.parse import urlencode

        return f"{base}?{urlencode({'next': next_url})}"
    return base


def _css_loader() -> Any:
    """Template helper: emit the ``<link>`` tag for the bundled OAuth buttons CSS."""
    from asok.templates import SafeString

    return SafeString(
        '<link rel="stylesheet" href="/css/oauth-buttons.css">'
    )


def _icon_helper(provider: str) -> Any:
    """Template helper: return the inline SVG monogram for ``provider``."""
    from asok.templates import SafeString

    return SafeString(get_icon(provider))


__all__ = [
    "AsokAuthProvidersExtension",
    "EXTRA_PROVIDERS",
    "NEXT_SESSION_KEY",
    "PROVIDER_ICONS",
    "PROVIDER_LABELS",
    "STATE_SESSION_KEY",
    "callback_for",
    "complete_oauth_flow",
    "get_icon",
    "pop_next_url",
    "register_extra_providers",
    "start_oauth_flow",
]
