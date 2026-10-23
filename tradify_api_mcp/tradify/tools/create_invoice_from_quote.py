"""Create invoice from quote: a draft Invoice copied from a quote, whole or in part (Breeze SaveChanges).

The modes are the panel's "Invoice from quote" choices (InvoiceHelper in the bundle): entire copies every line,
line_items the chosen ones; percentage, fixed_amount and remaining make one misc line of that amount (with tax)
at the quote's tax rate. Already invoiced is the sum the quote's other invoices copied from it.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

from tradify_api_mcp.core.errors import ErrorCode, ToolError
from tradify_api_mcp.core.tools import tool
from tradify_api_mcp.tradify.tools._api import (
    EMPTY_ID,
    INVOICE_CANCELLED,
    TAX_EXCLUSIVE,
    Api,
    app_date,
    deref,
    entity,
    iso_date,
    money,
    new_id,
    objects,
    round_money,
)
from tradify_api_mcp.tradify.tools._quotes import line_amounts, tax_rows, totals

if TYPE_CHECKING:
    from tradify_api_mcp.core.context import ToolContext

MODES = {"entire": 1, "line_items": 2, "percentage": 3, "fixed_amount": 4, "remaining": 5}
INVOICEABLE = (2, 3)  # approved (awaiting acceptance) and accepted
MISC, BOM = 3, 4

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "quote_id": {"type": "string", "minLength": 1, "description": "Quote ID from list_quotes."},
        "mode": {"type": "string", "enum": list(MODES)},
        "amount": {
            "type": "number",
            "exclusiveMinimum": 0,
            "description": "percentage: percent of the quote total (e.g. 50). fixed_amount: amount with tax.",
        },
        "lines": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "integer", "minimum": 1},
            "description": "line_items: positions of the quote's lines to invoice, 1 for the first.",
        },
    },
    "required": ["quote_id", "mode"],
    "additionalProperties": False,
}

EXAMPLE_RESPONSE: dict[str, Any] = {
    "invoice_id": "6c2e8f4a-1b3d-4e5f-8a9b-0c1d2e3f4a5b",
    "number": "Draft",
    "quote_id": "a9bed199-5dcc-4fa4-b9b1-aeb1cacb0c31",
    "status": "draft",
    "lines": [{"description": "50% of quote QT00002", "quantity": 1.0, "unit_price": 510.0, "amount": 510.0}],
    "subtotal": 510.0,
    "tax": 30.6,
    "total": 540.6,
    "due_date": "2026-10-30",
    "quote_invoiced_before": 0.0,
}


def due_date(kind: Any, ordinal: Any, day: date) -> date:
    """DueDateHelper.calculateDueDate: 1 day N of next month, 2 N days after, 3 day N of this month."""
    n = int(ordinal or 0)
    if kind == 2:
        return day + timedelta(days=n)
    if kind in (1, 3):
        first = day.replace(day=1)
        if kind == 1:
            first = (first + timedelta(days=32)).replace(day=1)
        last = ((first + timedelta(days=32)).replace(day=1) - timedelta(days=1)).day
        target = first.replace(day=min(n if 1 <= n <= 31 else 1, last))
        return max(target, day)
    return day


@tool(
    name="create_invoice_from_quote",
    title="Create invoice from quote",
    access="write",
    description="Draft invoice from an approved or accepted quote, for all of it or part of it.",
    details=(
        "Creates a draft invoice from a quote, as Create Invoice > From Quote does, linked to the quote and its "
        "job. mode entire copies every line; line_items copies the lines at the positions in lines; percentage "
        "invoices amount percent of the quote total; fixed_amount invoices amount (with tax); remaining invoices "
        "what the quote's earlier invoices did not. A part is one line at the quote's tax rate. Due date follows "
        "the customer's or your payment terms. The invoice stays a draft until send_invoice. Needs a plan with "
        "progress invoicing (Pro) for the part modes."
    ),
    input_schema=INPUT_SCHEMA,
    route="POST /quotes/{quote_id}/invoices",
    example_response=EXAMPLE_RESPONSE,
)
async def create_invoice_from_quote(ctx: ToolContext, args: dict[str, Any]) -> Any:
    api = Api(ctx)
    quote_id, mode = str(args["quote_id"]), str(args["mode"])
    body = await api.post("Invoice/GetNewInvoiceData", {"jobIds": [], "estimateIds": [quote_id], "customerId": None})
    found = objects(body)
    quotes = [deref(q, found) for q in (body or {}).get("Estimates") or []]
    quote = next((q for q in quotes if q.get("Id") == quote_id), None)
    if quote is None:
        raise ToolError("Tradify has no quote with this id (list_quotes).", ErrorCode.INVALID_INPUT)
    if int(quote.get("Status") or 0) not in INVOICEABLE:
        raise ToolError("Only an approved or accepted quote can be invoiced (send_quote).", ErrorCode.INVALID_INPUT)
    lines = sorted((deref(x, found) for x in quote.get("EstimateLines") or []), key=lambda x: x.get("SortOrder") or 0)
    if not lines:
        raise ToolError("The quote has no lines to invoice.", ErrorCode.INVALID_INPUT)
    before = [deref(i, found) for i in quote.get("Invoices") or []]
    invoiced = round_money(
        sum(money(i.get("AmountCopiedFromEstimate")) for i in before if i.get("Status") != INVOICE_CANCELLED)
    )
    total = money(quote.get("Total"))
    left = round_money(total - invoiced)
    method = int(quote.get("TaxCalculationMethodId") or TAX_EXCLUSIVE)
    invoice_id = new_id()
    number = quote.get("EstimateNumber")
    rows: list[tuple[dict[str, Any], dict[str, Any]]] = []  # (estimate line or {}, invoice line fields)

    def copy(line: dict[str, Any]) -> dict[str, Any]:
        if int(line.get("CostType") or 0) == BOM:
            raise ToolError("Quotes with kits cannot be invoiced line by line yet.", ErrorCode.INVALID_INPUT)
        fields = {"CostType": int(line.get("CostType") or MISC)}
        for key in ("WorkTypeId", "ProductId"):
            if line.get(key):
                fields[key] = line[key]
        return {
            **fields,
            "Description": line.get("Description"),
            "Quantity": float(line.get("Quantity") or 0),
            "UnitPrice": float(line.get("UnitPrice") or 0),
            "TaxRatePercentage": float(line.get("TaxRatePercentage") or 0),
            "TaxRateDescription": line.get("TaxRateDescription"),
        }

    if mode == "entire":
        rows = [(line, copy(line)) for line in lines]
        copied = total
    elif mode == "line_items":
        positions = args.get("lines") or []
        if not positions or max(positions) > len(lines):
            raise ToolError(f"lines must be positions from 1 to {len(lines)}.", ErrorCode.INVALID_INPUT)
        chosen = [lines[p - 1] for p in sorted(set(positions))]
        rows = [(line, {**copy(line), "EstimateLineId": line.get("Id")}) for line in chosen]
        copied = round_money(
            sum(money(x.get("Amount")) + (money(x.get("Tax")) if method == TAX_EXCLUSIVE else 0) for x in chosen)
        )
    else:
        if mode == "remaining":
            copied, text = left, f"Remaining portion of quote {number}"
        elif args.get("amount") is None:
            raise ToolError(f"mode {mode} needs amount.", ErrorCode.INVALID_INPUT)
        elif mode == "percentage":
            percent = float(args["amount"])
            copied, text = round_money(total * percent / 100), f"{percent:g}% of quote {number}"
        else:
            copied = round_money(float(args["amount"]))
            text = f"${copied:,.2f} portion of quote {number}"
        if copied <= 0 or copied > left + 0.005:
            raise ToolError(
                f"The quote total is {total:.2f}, {invoiced:.2f} is invoiced already; at most {left:.2f} is left.",
                ErrorCode.INVALID_INPUT,
            )
        first = lines[0]
        rate = float(first.get("TaxRatePercentage") or 0)
        unit = round(copied / (1 + rate), 4) if method == TAX_EXCLUSIVE else copied
        rows = [
            (
                {},
                {
                    "CostType": MISC,
                    "Description": text,
                    "Quantity": 1.0,
                    "UnitPrice": unit,
                    "TaxRatePercentage": rate,
                    "TaxRateDescription": first.get("TaxRateDescription"),
                },
            )
        ]
    invoice_lines = []
    for order, (_, fields) in enumerate(rows, start=1):
        amounts = line_amounts(fields["Quantity"], fields["UnitPrice"], 0.0, fields["TaxRatePercentage"], method)
        amounts.pop("CostAmount")
        amounts.pop("GrossProfit")
        invoice_lines.append(
            {
                "Id": new_id(),
                "InvoiceId": invoice_id,
                **fields,
                **amounts,
                "SortOrder": order,
                "TenantId": EMPTY_ID,
            }
        )
    options = await api.options()
    taxes = tax_rows(invoice_lines, method, bool(options.get("CalcaulteTaxOnLineItems")))
    sums = totals(invoice_lines, taxes, method)
    for key in ("Cost", "GrossProfit"):
        sums.pop(key)
    customer = deref(quote.get("Customer") or {}, found)
    today = await api.today()
    if customer.get("DueDateScheduleTypeId") is not None and customer.get("DueDateOrdinal") is not None:
        due = due_date(customer["DueDateScheduleTypeId"], customer["DueDateOrdinal"], today)
    else:
        due = due_date(options.get("DefaultDueDateScheduleTypeId"), options.get("DefaultDueDateOrdinal"), today)
    invoice: dict[str, Any] = {
        "Id": invoice_id,
        "InvoiceNumber": "Draft",
        "InvoiceSequence": 0,
        "CustomerId": quote.get("CustomerId"),
        "CustomerLocationId": quote.get("CustomerLocationId"),
        "CustomerRef": quote.get("CustomerRef"),
        "Description": quote.get("Description"),
        "FormattedDescription": quote.get("FormattedDescription"),
        "InvoiceDate": app_date(today),
        "DueDate": app_date(due),
        "Status": 1,
        "PriceGroupId": quote.get("PriceGroupId"),
        "DocumentFormatId": quote.get("DocumentFormatId") or options.get("DefaultDocumentFormatId"),
        "TaxCalculationMethodId": method,
        "IsTaxExempt": bool(quote.get("IsTaxExempt")),
        "IsSentToCustomer": False,
        "IsSentToAccountingSoftware": False,
        "IsFullyPaid": False,
        "Paid": 0.0,
        "Due": sums["Total"],
        "AmountCredited": 0.0,
        "EstimateId": quote_id,
        "AmountCopiedFromEstimate": copied,
        "InvoiceTypeId": MODES[mode],
        "IncludePaymentDetails": False,
        "IncludeSurcharge": False,
        "AutomaticReminderEnabled": False,
        "SiteSMSReminderEnabled": False,
        "CustomerSMSReminderEnabled": False,
        "DRCEnabled": False,
        "SyncAttempts": 0,
        "TenantId": EMPTY_ID,
        **sums,
        **await api.created(),
    }
    entities = [
        entity("Invoice", "Invoices", invoice),
        *(entity("InvoiceLine", "InvoiceLines", line) for line in invoice_lines),
        *(
            entity(
                "InvoiceTaxTotal",
                "InvoiceTaxTotals",
                {"Id": new_id(), "InvoiceId": invoice_id, "TenantId": EMPTY_ID, **t},
            )
            for t in taxes
        ),
    ]
    if quote.get("JobId"):
        link = {"Id": new_id(), "InvoiceId": invoice_id, "JobId": quote["JobId"], "TenantId": EMPTY_ID}
        entities.append(entity("InvoiceJob", "InvoiceJobs", link))
    saved = await api.save(entities)
    stored = next((e for e in saved if e.get("Id") == invoice_id), {})
    return {
        "invoice_id": invoice_id,
        "number": stored.get("InvoiceNumber") or "Draft",
        "quote_id": quote_id,
        "status": "draft",
        "lines": [
            {
                "description": line["Description"],
                "quantity": line["Quantity"],
                "unit_price": line["UnitPrice"],
                "amount": line["Amount"],
            }
            for line in invoice_lines
        ],
        "subtotal": sums["SubTotal"],
        "tax": sums["Tax"],
        "total": sums["Total"],
        "due_date": iso_date(invoice["DueDate"]),
        "quote_invoiced_before": invoiced,
    }
