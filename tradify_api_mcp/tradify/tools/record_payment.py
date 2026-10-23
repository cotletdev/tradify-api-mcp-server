"""Record payment: an InvoicePayment on an approved invoice plus the invoice's new Paid and Due (SaveChanges)."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from tradify_api_mcp.core.errors import ErrorCode, ToolError
from tradify_api_mcp.core.tools import tool
from tradify_api_mcp.tradify.tools._api import (
    EMPTY_ID,
    INVOICE_APPROVED,
    MODIFIED,
    Api,
    app_time,
    deref,
    entity,
    money,
    new_id,
    own,
    round_money,
)
from tradify_api_mcp.tradify.tools._invoices import invoice_detail

if TYPE_CHECKING:
    from tradify_api_mcp.core.context import ToolContext

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "invoice_id": {"type": "string", "minLength": 1, "description": "Invoice ID from list_invoices."},
        "amount": {"type": "number", "exclusiveMinimum": 0, "description": "Amount received, at most the amount due."},
        "date": {"type": "string", "format": "date", "description": "Payment date. Default: today."},
        "method": {
            "type": "string",
            "description": "Payment method name, e.g. Bank Deposit, Cash, Credit Card. Default: Unknown.",
        },
        "reference": {"type": "string", "maxLength": 255, "description": "e.g. the check number."},
    },
    "required": ["invoice_id", "amount"],
    "additionalProperties": False,
}

EXAMPLE_RESPONSE: dict[str, Any] = {
    "invoice_id": "558f2199-6ca6-489e-bfdf-d4d11cd878e3",
    "payment_id": "9e3b7c1d-2a4f-4e6b-8c0d-1f2e3a4b5c6d",
    "amount": 100.0,
    "date": "2026-10-23",
    "method": "Bank Deposit",
    "paid": 400.0,
    "due": 209.5,
    "status": "approved",
}


@tool(
    name="record_payment",
    title="Record payment",
    access="write",
    description="Record a payment received against an invoice and reduce the amount due.",
    details=(
        "Adds a payment you already received to an approved invoice, as Add Payment does: amount, date, method "
        "(by name, from Settings > Payment Methods) and a reference. It charges nobody and emails nobody. The "
        "amount cannot exceed what is due; paying it all marks the invoice paid. If an accounting app is connected, "
        "Tradify syncs the payment to it."
    ),
    input_schema=INPUT_SCHEMA,
    route="POST /invoices/{invoice_id}/payments",
    example_response=EXAMPLE_RESPONSE,
)
async def record_payment(ctx: ToolContext, args: dict[str, Any]) -> Any:
    api = Api(ctx)
    invoice, body, found = await invoice_detail(api, str(args["invoice_id"]))
    if int(invoice.get("Status") or 0) != INVOICE_APPROVED:
        raise ToolError("Payments go on an approved invoice; approve it with send_invoice.", ErrorCode.INVALID_INPUT)
    total, credited = money(invoice.get("Total")), money(invoice.get("AmountCredited"))
    payments = [deref(p, found) for p in invoice.get("InvoicePayments") or []]
    paid_before = round_money(sum(money(p.get("Amount")) for p in payments))
    due_before = round_money(total - paid_before - credited)
    amount = round_money(float(args["amount"]))
    if amount > due_before + 0.005:
        raise ToolError(f"The invoice has {due_before:.2f} due; the payment cannot be more.", ErrorCode.INVALID_INPUT)
    lookup = deref(body.get("LookupData") or {}, found)
    methods = [deref(m, found) for m in lookup.get("InvoicePaymentMethods") or []]
    methods = [m for m in methods if not m.get("IsArchived")]
    name = str(args.get("method") or "")
    method = next((m for m in methods if str(m.get("Description")).lower() == name.lower()), None) if name else None
    if name and method is None:
        known = ", ".join(str(m.get("Description")) for m in methods)
        raise ToolError(f"No payment method {name!r}. Methods: {known}.", ErrorCode.INVALID_INPUT)
    method = method or next((m for m in methods if m.get("DefaultPaymentMethod")), None)
    method = method or next((m for m in methods if str(m.get("Description")).lower() == "unknown"), methods[0])
    now = await api.now()
    when = now
    if args.get("date"):
        try:
            day = date.fromisoformat(str(args["date"]))
        except ValueError as exc:
            raise ToolError("date must be YYYY-MM-DD.", ErrorCode.INVALID_INPUT) from exc
        when = now.replace(year=day.year, month=day.month, day=day.day)
    payment = {
        "Id": new_id(),
        "InvoiceId": invoice.get("Id"),
        "Amount": amount,
        "PaymentDate": app_time(when),
        "InvoicePaymentMethodId": method.get("Id"),
        "PaymentRef": args.get("reference"),
        "TenantId": EMPTY_ID,
        **await api.created(),
    }
    paid = round_money(paid_before + amount)
    due = round_money(total - paid - credited)
    fully = paid + credited >= total
    fields = own(invoice)
    original = {"Paid": fields.get("Paid"), "Due": fields.get("Due"), "IsFullyPaid": fields.get("IsFullyPaid")}
    fields.update({"Paid": paid, "Due": due, "IsFullyPaid": fully})
    await api.save(
        [
            entity("Invoice", "Invoices", fields, MODIFIED, original),
            entity("InvoicePayment", "InvoicePayments", payment),
        ]
    )
    return {
        "invoice_id": invoice.get("Id"),
        "payment_id": payment["Id"],
        "amount": amount,
        "date": when.date().isoformat(),
        "method": method.get("Description"),
        "paid": paid,
        "due": due,
        "status": "paid" if fully else "approved",
    }
