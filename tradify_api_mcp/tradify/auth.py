"""Who is signed in: the panel's start-up answer (GetAppStateInfo), for "Signed in as ..."."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tradify_api_mcp.core.errors import AuthExpiredError
from tradify_api_mcp.tradify.client import app_state, breeze_objects, deref

if TYPE_CHECKING:
    from tradify_api_mcp.core.context import ToolContext


def account_name(state: dict[str, Any]) -> str | None:
    """The account as "Full Name (Company)" from a GetAppStateInfo answer, also for signup.py and login.py."""
    staff = deref(state.get("StaffMember") or {}, breeze_objects(state))
    name = staff.get("FullName")
    session = state.get("SessionInfo") or {}
    companies = session.get("Companies") or []
    company = next((c.get("CompanyName") for c in companies if c.get("Id") == session.get("CompanyId")), None)
    company = company or (companies[0].get("CompanyName") if companies else None)
    if name and company:
        return f"{name} ({company})"
    return name or company or None


async def whoami(ctx: ToolContext) -> str | None:
    """None only when Tradify says signed out; any other failure raises (detection tries again later)."""
    try:
        state = await app_state(ctx)
    except AuthExpiredError:
        return None
    return account_name(state)
