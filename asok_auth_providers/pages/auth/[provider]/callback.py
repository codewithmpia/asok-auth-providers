from __future__ import annotations

from asok import Request
from asok.auth import AuthError
from asok.exceptions import RedirectException

from asok_auth_providers.flow import complete_oauth_flow, pop_next_url


def get(request: Request):
    provider = request.params.get("provider", "")
    app = request.environ.get("asok.app")
    ext = getattr(app, "_auth_providers_ext", None) if app else None
    failed_redirect = ext.login_failed_redirect if ext else "/login"
    success_redirect = ext.login_redirect if ext else "/"

    try:
        user_info = complete_oauth_flow(request, provider)
    except AuthError as e:
        request.flash("error", str(e))
        raise RedirectException(failed_redirect)

    if ext and ext.on_login:
        try:
            ext.on_login(request, user_info)
        except RedirectException:
            raise
        except Exception as e:  # noqa: BLE001
            request.flash("error", f"Login failed: {e}")
            raise RedirectException(failed_redirect)
    else:
        # No on_login hook wired: stash the result in the session so the
        # consuming application can pick it up.
        request.session["oauth_user_info"] = user_info

    raise RedirectException(pop_next_url(request, success_redirect))
