from __future__ import annotations

from asok import Request
from asok.auth import AuthError
from asok.exceptions import RedirectException

from asok_auth_providers.flow import start_oauth_flow


def get(request: Request):
    provider = request.params.get("provider", "")
    next_url = request.args.get("next")
    try:
        url = start_oauth_flow(request, provider, next_url=next_url)
    except AuthError as e:
        request.flash("error", str(e))
        app = request.environ.get("asok.app")
        ext = getattr(app, "_auth_providers_ext", None)
        raise RedirectException(ext.login_failed_redirect if ext else "/login")
    raise RedirectException(url)
