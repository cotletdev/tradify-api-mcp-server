"""Get quote: one quote with lines, tax and the invoices made from it (Estimate/GetEstimateDetailData)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tradify_api_mcp.core.tools import tool
from tradify_api_mcp.tradify.tools._api import Api, deref, iso_date, money
from tradify_api_mcp.tradify.tools._invoices import invoice_status
from tradify_api_mcp.tradify.tools._quotes import quote_detail, quote_status

if TYPE_CHECKING:
    from tradify_api_mcp.core.context import ToolContext

# EstimateLine.CostType of the bundle.
LINE_TYPES = {1: "item", 2: "time", 3: "misc", 4: "kit"}

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"quote_id": {"type": "string", "minLength": 1, "description": "Quote ID from list_quotes."}},
    "required": ["quote_id"],
    "additionalProperties": False,
}

EXAMPLE_RESPONSE: dict[str, Any] = {
    "quote_id": "89d70250-7c33-43f9-8311-966f32cd9559",
    "number": "QT00001",
    "status": "accepted",
    "customer_id": "7801cbcd-8d5b-4506-afaa-011550798969",
    "customer": "Riverside Dental Clinic",
    "job_id": "d3bd2e39-af25-4cda-9daf-d9f758f8f0e5",
    "job": "JB00001",
    "reference": "RD-1042",
    "description": "Replace leaking water heater in staff kitchen",
    "quote_date": "2026-10-23",
    "expiry_date": "2026-11-22",
    "accepted_on": "2026-10-23",
    "lines": [
        {
            "type": "misc",
            "description": "Supply and install 50 gal water heater",
            "quantity": 1.0,
            "unit_price": 1150.0,
            "unit_cost": 650.0,
            "tax_rate": "6% Sales Tax",
            "amount": 1150.0,
        }
    ],
    "subtotal": 1150.0,
    "tax": 69.0,
    "total": 1219.0,
    "cost": 650.0,
    "gross_profit": 500.0,
    "invoices": [
        {
            "invoice_id": "558f2199-6ca6-489e-bfdf-d4d11cd878e3",
            "number": "IV00001",
            "status": "approved",
            "total": 609.5,
        }
    ],
}


@tool(
    name="get_quote",
    title="Get quote",
    access="read",
    description="Full quote: lines with price and cost, tax, totals, gross profit, dates and invoices made from it.",
    details=(
        "Returns one quote: status (draft, awaiting_acceptance, accepted, declined, cancelled, expired), customer, "
        "job, reference, description, quote, expiry and acceptance dates, its lines (item, time, misc or kit, with "
        "quantity, unit price, unit cost, tax rate and amount), subtotal, tax, total, cost and gross profit, and the "
        "invoices made from it so far."
    ),
    input_schema=INPUT_SCHEMA,
    route="GET /quotes/{quote_id}",
    example_response=EXAMPLE_RESPONSE,
)
async def get_quote(ctx: ToolContext, args: dict[str, Any]) -> Any:
    api = Api(ctx)
    quote, _, found = await quote_detail(api, str(args["quote_id"]))
    today = await api.today()
    customer = deref(quote.get("Customer") or {}, found)
    job = deref(quote.get("Job") or {}, found)
    lines = sorted((deref(x, found) for x in quote.get("EstimateLines") or []), key=lambda x: x.get("SortOrder") or 0)
    invoices = [deref(i, found) for i in quote.get("Invoices") or []]
    return {
        "quote_id": quote.get("Id"),
        "number": quote.get("EstimateNumber"),
        "status": quote_status(int(quote.get("Status") or 0), quote.get("ExpiryDate"), today),
        "customer_id": quote.get("CustomerId"),
        "customer": customer.get("CustomerName"),
        "job_id": quote.get("JobId"),
        "job": job.get("JobNumber"),
        "reference": quote.get("CustomerRef"),
        "description": str(quote.get("Description") or "").strip(),
        "quote_date": iso_date(quote.get("EstimateDate")),
        "expiry_date": iso_date(quote.get("ExpiryDate")),
        "accepted_on": iso_date(quote.get("AcceptedOn")),
        "lines": [
            {
                "type": LINE_TYPES.get(int(line.get("CostType") or 0), "misc"),
                "description": line.get("Description"),
                "quantity": line.get("Quantity"),
                "unit_price": money(line.get("UnitPrice")),
                "unit_cost": money(line.get("UnitCost")),
                "tax_rate": line.get("TaxRateDescription"),
                "amount": money(line.get("Amount")),
            }
            for line in lines
        ],
        "subtotal": money(quote.get("SubTotal")),
        "tax": money(quote.get("Tax")),
        "total": money(quote.get("Total")),
        "cost": money(quote.get("Cost")),
        "gross_profit": money(quote.get("GrossProfit")),
        "invoices": [
            {
                "invoice_id": i.get("Id"),
                "number": i.get("InvoiceNumber"),
                "status": invoice_status(i, today),
                "total": money(i.get("Total")),
            }
            for i in invoices
            if i.get("Id")
        ],
    }
