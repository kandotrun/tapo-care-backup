"""Region helpers for TP-Link/Tapo NBU endpoints."""
from __future__ import annotations

import re

DEFAULT_REGION = "aps1"

_REGION_RE = re.compile(r"https?://([a-z]+\d+)-app-(?:server|cloudgateway)\.")


def region_from_app_server_url(app_server_url: str | None, default: str = DEFAULT_REGION) -> str:
    """Extract `aps1`/`euw1`/`use1` from a TP-Link app server URL.

    Japan and nearby APAC accounts usually resolve to `aps1`. We default there
    because it is the most useful fallback for this repository's owner.
    """
    if not app_server_url:
        return default
    match = _REGION_RE.search(app_server_url)
    return match.group(1) if match else default


def care_base_url(region: str | None = None) -> str:
    """Return the regional Tapo Care app API base URL."""
    return f"https://{region or DEFAULT_REGION}-app-tapo-care.i.tplinknbu.com"


def app_server_url_for_region(region: str | None = None) -> str:
    """Return a best-effort regional app server URL for account/device APIs."""
    return f"https://{region or DEFAULT_REGION}-app-server.iot.i.tplinknbu.com"
