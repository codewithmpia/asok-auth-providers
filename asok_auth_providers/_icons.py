"""Provider icons loaded from the bundled ``icons/`` directory.

Each provider's ``<name>.svg`` file is read once at import time and cached
in :data:`ICONS`. The :func:`get_icon` helper returns the raw SVG markup
(wrapped in :class:`asok.templates.SafeString` by the extension's template
helper so it isn't HTML-escaped on render).

Providers without a bundled SVG fall back to a generic placeholder, so the
buttons still render even if a future provider lands before its asset.
"""
from __future__ import annotations

import os

_ICONS_DIR = os.path.join(os.path.dirname(__file__), "icons")

_FALLBACK = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" '
    'width="20" height="20" fill="none" aria-hidden="true">'
    '<circle cx="10" cy="10" r="9" stroke="currentColor" stroke-width="1.5"/>'
    '<text x="10" y="14" text-anchor="middle" font-family="system-ui,sans-serif" '
    'font-size="10" font-weight="700" fill="currentColor">?</text>'
    '</svg>'
)


def _load_bundled_icons() -> dict[str, str]:
    out: dict[str, str] = {}
    if not os.path.isdir(_ICONS_DIR):
        return out
    for fname in os.listdir(_ICONS_DIR):
        if not fname.endswith(".svg"):
            continue
        name = os.path.splitext(fname)[0].lower()
        path = os.path.join(_ICONS_DIR, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                out[name] = f.read()
        except OSError:
            continue
    return out


ICONS: dict[str, str] = _load_bundled_icons()


def get_icon(provider: str) -> str:
    """Return the bundled SVG for ``provider`` (or a generic fallback)."""
    return ICONS.get(provider.lower(), _FALLBACK)
