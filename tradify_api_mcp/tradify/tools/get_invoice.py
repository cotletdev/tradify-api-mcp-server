"""Get invoice: one invoice with lines, payments and its jobs (Invoice/GetInvoiceDetailData)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tradify_api_mcp.core.tools import tool
from tradify_api_mcp.tradify.tools._api import Api, deref, iso_date, money
from tradify_api_mcp.tradify.tools._invoices import invoice_detail, invoice_status

if TYPE_CHECKING:
    from tradify_api_mcp.core.context import ToolContext

# Invoice.InvoiceTypeId of the bundle: how the invoice was made.
INVOICE_TYPES = {1: "entire_quote", 2: "quote_line_items", 3: "percentage", 4: "fixed", 5: "remaining"}

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"invoice_id": {"type": "string", "minLength": 1, "description": "Invoice ID from list_invoices."}},
    "required": ["invoice_id"],
    "additionalProperties": False,
}

EXAMPLE_RESPONSE: dict[str, Any] = {
    "invoice_id": "558f2199-6ca6-489e-bfdf-d4d11cd878e3",
    "number": "IV00001",
    "status": "approved",
    "customer_id": "7801cbcd-8d5b-4506-afaa-011550798969",
    "customer": "Riverside Dental Clinic",
    "jobs": [{"job_id": "d3bd2e39-af25-4cda-9daf-d9f758f8f0e5", "number": "JB00001"}],
    "quote_id": "89d70250-7c33-43f9-8311-966f32cd9559",
    "made_from_quote": "percentage",
    "reference": "RD-1042",
    "description": "Replace leaking water heater in staff kitchen",
    "invoice_date": "2026-10-23",
    "due_date": "2026-10-30",
    "sent_to_customer": False,
    "lines": [
        {
            "description": "50% of quote QT00001",
            "quantity": 1.0,
            "unit_price": 575.0,
            "tax_rate": "6% Sales Tax",
            "amount": 575.0,
        }
    ],
    "subtotal": 575.0,
    "tax": 34.5,
    "total": 609.5,
    "paid": 450.0,
    "credited": 0.0,
    "due": 159.5,
    "payments": [{"date": "2026-10-23", "amount": 300.0, "method": "Bank Deposit", "reference": None}],
}


@tool(
    name="get_invoice",
    title="Get invoice",
    access="read",
    description="Full invoice: lines, tax, totals, every payment with date and method, amount due, jobs and quote.",
    details=(
        "Returns one invoice: status (draft, approved, overdue, paid, cancelled), customer, its jobs, the quote it "
        "came from and how (entire_quote, quote_line_items, percentage, fixed, remaining), reference, description, "
        "invoice and due dates, whether it was sent, its lines, subtotal, tax, total, paid, credited and due, and "
        "each payment with date, amount, method and reference."
    ),
    input_schema=INPUT_SCHEMA,
    route="GET /invoices/{invoice_id}",
    example_response=EXAMPLE_RESPONSE,
)
async def get_invoice(ctx: ToolContext, args: dict[str, Any]) -> Any:
    api = Api(ctx)
    invoice, body, found = await invoice_detail(api, str(args["invoice_id"]))
    customer = deref(invoice.get("Customer") or {}, found)
    lookup = deref(body.get("LookupData") or {}, found)
    rows = [deref(x, found) for x in lookup.get("InvoicePaymentMethods") or []]
    methods = {m.get("Id"): m.get("Description") for m in rows}
    links = [deref(j, found) for j in invoice.get("InvoiceJobs") or []]
    lines = sorted((deref(x, found) for x in invoice.get("InvoiceLines") or []), key=lambda x: x.get("SortOrder") or 0)
    payments = sorted(
        (deref(p, found) for p in invoice.get("InvoicePayments") or []), key=lambda p: str(p.get("PaymentDate") or "")
    )
    made_from = INVOICE_TYPES.get(int(invoice.get("InvoiceTypeId") or 0))
    return {
        "invoice_id": invoice.get("Id"),
        "number": invoice.get("InvoiceNumber"),
        "status": invoice_status(invoice, await api.today()),
        "customer_id": invoice.get("CustomerId"),
        "customer": customer.get("CustomerName"),
        "jobs": [
            {"job_id": link.get("JobId"), "number": deref(link.get("Job") or {}, found).get("JobNumber")}
            for link in links
        ],
        "quote_id": invoice.get("EstimateId"),
        "made_from_quote": made_from if invoice.get("EstimateId") else None,
        "reference": invoice.get("CustomerRef"),
        "description": str(invoice.get("Description") or "").strip(),
        "invoice_date": iso_date(invoice.get("InvoiceDate")),
        "due_date": iso_date(invoice.get("DueDate")),
        "sent_to_customer": bool(invoice.get("IsSentToCustomer")),
        "lines": [
            {
                "description": line.get("Description"),
                "quantity": line.get("Quantity"),
                "unit_price": money(line.get("UnitPrice")),
                "tax_rate": line.get("TaxRateDescription"),
                "amount": money(line.get("Amount")),
            }
            for line in lines
        ],
        "subtotal": money(invoice.get("SubTotal")),
        "tax": money(invoice.get("Tax")),
        "total": money(invoice.get("Total")),
        "paid": money(invoice.get("Paid")),
        "credited": money(invoice.get("AmountCredited")),
        "due": money(invoice.get("Due")),
        "payments": [
            {
                "date": iso_date(p.get("PaymentDate")),
                "amount": money(p.get("Amount")),
                "method": methods.get(p.get("InvoicePaymentMethodId")),
                "reference": p.get("PaymentRef"),
            }
            for p in payments
        ],
    }
