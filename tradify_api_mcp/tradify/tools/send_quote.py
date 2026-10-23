"""Send quote: approve a draft quote (Estimate/ApproveEstimate, a GET that writes) and email it to the customer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tradify_api_mcp.core.errors import ErrorCode, ToolError
from tradify_api_mcp.core.tools import tool
from tradify_api_mcp.tradify.tools._api import Api, deref
from tradify_api_mcp.tradify.tools._quotes import quote_detail
from tradify_api_mcp.tradify.tools._send import ensure_email_allowed, fill, recipients, send, template

if TYPE_CHECKING:
    from tradify_api_mcp.core.context import ToolContext

DRAFT, APPROVED = 1, 2

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "quote_id": {"type": "string", "minLength": 1, "description": "Quote ID from list_quotes or create_quote."},
        "to": {
            "type": "array",
            "minItems": 1,
            "maxItems": 10,
            "items": {"type": "string"},
            "description": "Recipient emails. Default: the customer's email.",
        },
        "subject": {"type": "string", "maxLength": 100, "description": "Default: your quote email template."},
        "message": {"type": "string", "maxLength": 5000, "description": "Email text. Default: your quote template."},
        "send_me_a_copy": {"type": "boolean", "default": False},
    },
    "required": ["quote_id"],
    "additionalProperties": False,
}

EXAMPLE_RESPONSE: dict[str, Any] = {
    "quote_id": "a9bed199-5dcc-4fa4-b9b1-aeb1cacb0c31",
    "number": "QT00002",
    "status": "awaiting_acceptance",
    "emailed_to": ["orders@example.com"],
    "subject": "Quotation QT00002 from Carter Plumbing Co.",
}


async def _plan(api: Api, args: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[str]]:
    quote, body, found = await quote_detail(api, str(args["quote_id"]))
    if int(quote.get("Status") or 0) not in (DRAFT, APPROVED):
        raise ToolError(
            "Only a draft or approved quote can be sent; this one is accepted, declined or cancelled.",
            ErrorCode.INVALID_INPUT,
        )
    await ensure_email_allowed(api)
    customer = deref(quote.get("Customer") or {}, found)
    to = recipients(args.get("to"), customer.get("Email"))
    return quote, body, found, to


async def check_send_quote(ctx: ToolContext, args: dict[str, Any]) -> None:
    await _plan(Api(ctx), args)


@tool(
    name="send_quote",
    title="Send quote",
    access="write",
    confirm=True,
    description="Approve the quote and email it to the customer with a link to accept or decline online.",
    details=(
        "Approves a draft quote (it becomes awaiting acceptance) and emails it from Tradify with the link where the "
        "customer accepts or declines it online. Without to it goes to the customer's email. Subject and text "
        "default to your quote email template. An approved quote can be sent again. Tradify sends this mail only "
        "when the login has 2-Step Security set up; otherwise the call stops before approving. By default you "
        "confirm each call, and you can switch that off for this tool."
    ),
    input_schema=INPUT_SCHEMA,
    route="POST /quotes/{quote_id}/send",
    example_response=EXAMPLE_RESPONSE,
    check=check_send_quote,
)
async def send_quote(ctx: ToolContext, args: dict[str, Any]) -> Any:
    api = Api(ctx)
    quote, body, found, to = await _plan(api, args)
    quote_id = str(quote.get("Id"))
    if int(quote.get("Status") or 0) == DRAFT:
        await api.get("Estimate/ApproveEstimate", {"estimateId": quote_id})
        quote, body, found = await quote_detail(api, quote_id)
    if int(quote.get("Status") or 0) != APPROVED:
        raise ToolError("Tradify did not approve the quote.", ErrorCode.TARGET_ERROR)
    options = await api.options()
    customer = deref(quote.get("Customer") or {}, found)
    values = {
        "companyname": str(options.get("CompanyName") or ""),
        "sender": str((await api.staff()).get("FullName") or ""),
        "number": str(quote.get("EstimateNumber") or ""),
        "total": f"${float(quote.get('Total') or 0):,.2f}",
        "customername": str(customer.get("CustomerName") or ""),
    }
    lookup = deref(body.get("LookupData") or {}, found)
    chosen = template(lookup, found, "quote")
    subject = args.get("subject") or fill(str(chosen.get("Subject") or "Quote [number]"), values)
    message = args.get("message") or fill(str(chosen.get("Body") or ""), values)
    await send(api, "quote", quote_id, to, subject, message, bool(args.get("send_me_a_copy")))
    return {
        "quote_id": quote_id,
        "number": quote.get("EstimateNumber"),
        "status": "awaiting_acceptance",
        "emailed_to": to,
        "subject": subject,
    }
