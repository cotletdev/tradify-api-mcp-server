"""Send invoice: approve a draft invoice (Invoice/ApproveInvoice, a GET that writes) and email it to the customer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tradify_api_mcp.core.errors import ErrorCode, ToolError
from tradify_api_mcp.core.tools import tool
from tradify_api_mcp.tradify.tools._api import INVOICE_APPROVED, INVOICE_DRAFT, Api, deref, iso_date, money
from tradify_api_mcp.tradify.tools._invoices import invoice_detail
from tradify_api_mcp.tradify.tools._send import ensure_email_allowed, fill, recipients, send, template

if TYPE_CHECKING:
    from tradify_api_mcp.core.context import ToolContext

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "invoice_id": {
            "type": "string",
            "minLength": 1,
            "description": "Invoice ID from list_invoices or create_invoice_from_quote.",
        },
        "to": {
            "type": "array",
            "minItems": 1,
            "maxItems": 10,
            "items": {"type": "string"},
            "description": "Recipient emails. Default: the customer's email.",
        },
        "subject": {"type": "string", "maxLength": 100, "description": "Default: your invoice email template."},
        "message": {"type": "string", "maxLength": 5000, "description": "Email text. Default: your invoice template."},
        "send_me_a_copy": {"type": "boolean", "default": False},
    },
    "required": ["invoice_id"],
    "additionalProperties": False,
}

EXAMPLE_RESPONSE: dict[str, Any] = {
    "invoice_id": "6c2e8f4a-1b3d-4e5f-8a9b-0c1d2e3f4a5b",
    "number": "IV00002",
    "status": "approved",
    "emailed_to": ["orders@example.com"],
    "subject": "Invoice IV00002 from Carter Plumbing Co.",
    "total": 540.6,
    "due": 540.6,
    "due_date": "2026-10-30",
}


async def _plan(api: Api, args: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[str]]:
    invoice, body, found = await invoice_detail(api, str(args["invoice_id"]))
    if int(invoice.get("Status") or 0) not in (INVOICE_DRAFT, INVOICE_APPROVED):
        raise ToolError("A cancelled invoice cannot be sent.", ErrorCode.INVALID_INPUT)
    await ensure_email_allowed(api)
    customer = deref(invoice.get("Customer") or {}, found)
    to = recipients(args.get("to"), customer.get("Email"))
    return invoice, body, found, to


async def check_send_invoice(ctx: ToolContext, args: dict[str, Any]) -> None:
    await _plan(Api(ctx), args)


@tool(
    name="send_invoice",
    title="Send invoice",
    access="write",
    confirm=True,
    description="Approve the invoice and email it to the customer, with payment reminders if enabled.",
    details=(
        "Approves a draft invoice (Tradify gives it its number) and emails it from Tradify with the link to view "
        "and pay it; payment reminders follow if you enabled them. Without to it goes to the customer's email. "
        "Subject and text default to your invoice email template. An approved invoice can be sent again. Tradify "
        "sends this mail only when the login has 2-Step Security set up; otherwise the call stops before "
        "approving. By default you confirm each call, and you can switch that off for this tool."
    ),
    input_schema=INPUT_SCHEMA,
    route="POST /invoices/{invoice_id}/send",
    example_response=EXAMPLE_RESPONSE,
    check=check_send_invoice,
)
async def send_invoice(ctx: ToolContext, args: dict[str, Any]) -> Any:
    api = Api(ctx)
    invoice, body, found, to = await _plan(api, args)
    invoice_id = str(invoice.get("Id"))
    if int(invoice.get("Status") or 0) == INVOICE_DRAFT:
        await api.get("Invoice/ApproveInvoice", {"invoiceId": invoice_id})
        invoice, body, found = await invoice_detail(api, invoice_id)
    if int(invoice.get("Status") or 0) != INVOICE_APPROVED:
        raise ToolError("Tradify did not approve the invoice.", ErrorCode.TARGET_ERROR)
    options = await api.options()
    customer = deref(invoice.get("Customer") or {}, found)
    values = {
        "companyname": str(options.get("CompanyName") or ""),
        "sender": str((await api.staff()).get("FullName") or ""),
        "number": str(invoice.get("InvoiceNumber") or ""),
        "total": f"${money(invoice.get('Total')):,.2f}",
        "customername": str(customer.get("CustomerName") or ""),
    }
    lookup = deref(body.get("LookupData") or {}, found)
    chosen = template(lookup, found, "invoice")
    subject = args.get("subject") or fill(str(chosen.get("Subject") or "Invoice [number]"), values)
    message = args.get("message") or fill(str(chosen.get("Body") or ""), values)
    await send(api, "invoice", invoice_id, to, subject, message, bool(args.get("send_me_a_copy")))
    return {
        "invoice_id": invoice_id,
        "number": invoice.get("InvoiceNumber"),
        "status": "approved",
        "emailed_to": to,
        "subject": subject,
        "total": money(invoice.get("Total")),
        "due": money(invoice.get("Due")),
        "due_date": iso_date(invoice.get("DueDate")),
    }
