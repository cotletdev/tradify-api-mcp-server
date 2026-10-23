"""Quote and invoice email (Estimate/SendEstimateEmail, Invoice/SendInvoiceEmail), as the panel's Email dialog.

Tradify blocks this mail until the login has 2-Step Security: `GetAppStateInfo` says
`DeviceAuthenticationSetupCompleted` false and `Email/CheckEmailQuota` answers 403 `isEmailAccessBlocked`.
The tools check it before approving anything. Subject and text come from the company's email template with
the panel's placeholders filled (PlaceHolderHelper in the bundle).
"""

from __future__ import annotations

import re
from typing import Any

from tradify_api_mcp.core.errors import ErrorCode, ToolError
from tradify_api_mcp.tradify.tools._api import Api, deref, html_text

BLOCKED = (
    "Tradify blocks quote and invoice email on this login until 2-Step Security is set up. In Tradify, open "
    "Settings > Security (a user with Settings access) and set up 2-Step Security with a mobile number, then try again."
)
_EMAIL = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$")


def recipients(given: list[str] | None, customer_email: Any) -> list[str]:
    """The `to` list, or the customer's email (a comma list in Tradify)."""
    raw = given or [part for part in re.split(r"[,;]", str(customer_email or "")) if part.strip()]
    to = [address.strip() for address in raw]
    if not to:
        raise ToolError("The customer has no email; pass to.", ErrorCode.INVALID_INPUT)
    bad = [address for address in to if not _EMAIL.match(address)]
    if bad:
        raise ToolError(f"Not an email address: {', '.join(bad)}.", ErrorCode.INVALID_INPUT)
    return to


async def ensure_email_allowed(api: Api) -> None:
    if await api.email_blocked():
        raise ToolError(BLOCKED, ErrorCode.APP_PERMISSION_DENIED)


def template(lookup: dict[str, Any], found: dict[str, dict[str, Any]], name: str) -> dict[str, Any]:
    templates = [deref(t, found) for t in lookup.get("EmailTemplates") or []]
    return next((t for t in templates if str(t.get("Description")).lower() == name and not t.get("IsArchived")), {})


def fill(text: str, values: dict[str, str]) -> str:
    """Replace [placeholder] tokens the way the panel does (case-insensitive)."""
    for key, value in values.items():
        text = re.sub(re.escape(f"[{key}]"), lambda _, v=value: v, text, flags=re.IGNORECASE)
    return text


async def send(
    api: Api,
    kind: str,
    record_id: str,
    to: list[str],
    subject: str,
    message: str,
    copy_me: bool,
) -> None:
    """POST the panel's send-email call; a 403 here is the 2-Step Security block."""
    staff = await api.staff()
    params = {
        f"{'estimate' if kind == 'quote' else 'invoice'}Id": record_id,
        "userName": staff.get("UserName"),
        "userEmail": staff.get("Email"),
        "to": ", ".join(to),
        "cC": None,
        "bCC": None,
        "subject": subject[:100],
        "message": html_text(message),
        "attachments": [],
        "emailSenderACopy": copy_me,
        "markAsSent": True,
    }
    path = "Estimate/SendEstimateEmail" if kind == "quote" else "Invoice/SendInvoiceEmail"
    try:
        await api.post(path, params)
    except ToolError as exc:
        if exc.code == ErrorCode.TARGET_BLOCKED:
            raise ToolError(BLOCKED, ErrorCode.APP_PERMISSION_DENIED) from exc
        raise
