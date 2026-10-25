"""Tradify panel requests, recorded 23.10.2026 on go.tradifyhq.com.

The panel ("Evo", a SPA) calls same-host `/api/*` as JSON. The session is the httpOnly cookie `SessionId`
alone: `GET /api/Common/GetAppStateInfo` answers 200 with it and 401 with an empty body without it (the
other cookies, `LoginId`, `CompanyId`, `DeviceId`, change nothing). Reads by GET need no header. Calls that
post (`/api/Settings/...`, `/api/SaveChanges/SaveChanges`) carry the panel's antiforgery token, which
`GetAppStateInfo` returns as `RequestVerificationToken`, in `requestverificationantiforgerytoken`, next to the
app's own `clientapiversion` and `version` numbers.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from tradify_api_mcp.core.errors import AuthExpiredError

if TYPE_CHECKING:
    from tradify_api_mcp.core.context import ToolContext

WEB = "https://go.tradifyhq.com"
STATE_URL = f"{WEB}/api/Common/GetAppStateInfo"
# Numbers the panel build of 23.10.2026 sends in `clientapiversion` and `version`.
CLIENT_API_VERSION = "71"
APP_VERSION = "374"


def breeze_objects(node: Any, found: dict[str, dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    """Every Breeze object of an answer by its `$id`, so a `{"$ref": "N"}` can be followed."""
    found = {} if found is None else found
    if isinstance(node, dict):
        if isinstance(node.get("$id"), str):
            found[node["$id"]] = node
        for value in node.values():
            breeze_objects(value, found)
    elif isinstance(node, list):
        for value in node:
            breeze_objects(value, found)
    return found


def deref(node: Any, objects: dict[str, dict[str, Any]]) -> Any:
    """The object a `$ref` points at; anything else as it is."""
    if isinstance(node, dict) and isinstance(node.get("$ref"), str):
        return objects.get(node["$ref"], {})
    return node


async def app_state(ctx: ToolContext) -> dict[str, Any]:
    """The panel's start-up answer. Raises `auth_expired` when the session is gone (HTTP 401)."""
    url = f"{STATE_URL}?clientUtcNow={quote(datetime.now(UTC).strftime('%Y/%m/%d %H:%M:%S'))}"
    response = await ctx.call("GET", url, headers={"referer": f"{WEB}/"})
    body: dict[str, Any] = response.json()
    if not (body.get("SessionInfo") or {}).get("IsAuthenticated"):
        raise AuthExpiredError("The app signed this account out. Sign in again in its Cloud Browser.")
    return body


def post_headers(state: dict[str, Any]) -> dict[str, str]:
    """Headers of a posting panel call from a GetAppStateInfo answer: antiforgery token and version numbers."""
    return {
        "requestverificationantiforgerytoken": str(state.get("RequestVerificationToken") or ""),
        "clientapiversion": CLIENT_API_VERSION,
        "version": APP_VERSION,
        "referer": f"{WEB}/",
        "refererfullurl": f"{WEB}/",
        "accept": "application/json, text/plain, */*",
    }


async def request_headers(ctx: ToolContext) -> dict[str, str]:
    """Headers of a posting panel call (`docker/prod-run request`): antiforgery token plus the app's version numbers."""
    return post_headers(await app_state(ctx))
