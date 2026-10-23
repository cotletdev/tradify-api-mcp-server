"""Create quote: a draft Estimate with its lines and tax rows through Breeze SaveChanges.

Lines are misc (description and price) or time (a billing rate, priced from the customer's price group).
The panel computes every amount and the server stores it, so the sums here follow the bundle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tradify_api_mcp.core.errors import ErrorCode, ToolError
from tradify_api_mcp.core.tools import tool
from tradify_api_mcp.tradify.tools._api import (
    EMPTY_ID,
    TAX_EXCLUSIVE,
    TAX_INCLUSIVE,
    Api,
    app_date,
    days_after,
    deref,
    entity,
    html_text,
    iso_date,
    new_id,
    objects,
)
from tradify_api_mcp.tradify.tools._jobs import customer_detail, job_detail
from tradify_api_mcp.tradify.tools._quotes import line_amounts, tax_rows, totals

if TYPE_CHECKING:
    from tradify_api_mcp.core.context import ToolContext

MISC, LABOUR = 3, 2

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "customer_id": {"type": "string", "minLength": 1, "description": "From list_customers or create_customer."},
        "line_items": {
            "type": "array",
            "minItems": 1,
            "maxItems": 100,
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["misc", "time"], "default": "misc"},
                    "description": {
                        "type": "string",
                        "maxLength": 4000,
                        "description": "Default for time: the rate's.",
                    },
                    "quantity": {"type": "number", "exclusiveMinimum": 0, "description": "Units, or hours for time."},
                    "unit_price": {
                        "type": "number",
                        "minimum": 0,
                        "description": "Price per unit before tax. Required for misc; time defaults to the rate.",
                    },
                    "unit_cost": {"type": "number", "minimum": 0, "description": "Your cost per unit. Default: 0."},
                    "billing_rate": {"type": "string", "description": "Time only: billing rate name. Default rate."},
                    "tax_rate": {"type": "string", "description": "Tax rate name, e.g. 'No Tax'. Default rate."},
                },
                "required": ["quantity"],
                "additionalProperties": False,
            },
        },
        "description": {"type": "string", "maxLength": 4000, "description": "Shown on the quote."},
        "reference": {"type": "string", "maxLength": 255, "description": "Customer reference."},
        "expiry_date": {"type": "string", "format": "date", "description": "Default: your expiry days setting."},
        "tax_inclusive": {"type": "boolean", "default": False, "description": "Prices include tax."},
        "job_id": {"type": "string", "description": "Link the quote to this customer's job (list_jobs)."},
    },
    "required": ["customer_id", "line_items"],
    "additionalProperties": False,
}

EXAMPLE_RESPONSE: dict[str, Any] = {
    "quote_id": "2a6d4c1b-7f3e-4b8a-9c5d-1e0f2a3b4c5d",
    "number": "QT00002",
    "status": "draft",
    "customer": "Maple Street Bakery",
    "job_id": None,
    "lines": [
        {"description": "Grease trap, 20 gal", "quantity": 1.0, "unit_price": 640.0, "amount": 640.0},
        {"description": "Labor", "quantity": 4.0, "unit_price": 95.0, "amount": 380.0},
    ],
    "subtotal": 1020.0,
    "tax": 61.2,
    "total": 1081.2,
    "quote_date": "2026-10-23",
    "expiry_date": "2026-11-22",
}


def _rate(rates: list[dict[str, Any]], name: str | None, default_id: Any) -> dict[str, Any]:
    if name:
        match = next((r for r in rates if str(r.get("Description") or "").lower() == name.lower()), None)
        if match is None:
            known = ", ".join(str(r.get("Description")) for r in rates)
            raise ToolError(f"No tax rate {name!r}. Rates: {known}.", ErrorCode.INVALID_INPUT)
        return match
    return next((r for r in rates if r.get("Id") == default_id), rates[0] if rates else {})


@tool(
    name="create_quote",
    title="Create quote",
    access="write",
    description="Draft quote with line items. Nothing is sent until you call send_quote.",
    details=(
        "Creates a draft quote for a customer, as New Quote does. Each line is misc (description, quantity, "
        "unit_price) or time (hours at a billing rate; the price comes from the customer's price group unless "
        "unit_price is given). Tax uses the default rate, or tax_rate by name; amounts, tax and totals are worked "
        "out as Tradify does. job_id links it to a job of the same customer. Expiry defaults to your expiry days "
        "setting. Price list items and kits are not supported yet. The quote stays a draft until send_quote."
    ),
    input_schema=INPUT_SCHEMA,
    route="POST /customers/{customer_id}/quotes",
    example_response=EXAMPLE_RESPONSE,
)
async def create_quote(ctx: ToolContext, args: dict[str, Any]) -> Any:
    api = Api(ctx)
    customer, _, _ = await customer_detail(api, str(args["customer_id"]), size=1)
    job: dict[str, Any] = {}
    if args.get("job_id"):
        job, _, _ = await job_detail(api, str(args["job_id"]))
        if job.get("CustomerId") != customer.get("Id"):
            raise ToolError("The job belongs to another customer.", ErrorCode.INVALID_INPUT)
    options = await api.options()
    lookup = await api.get("Estimate/GetEstimateLookupData", {"customerId": customer.get("Id")})
    found = objects(lookup)
    rates = [deref(r, found) for r in (lookup or {}).get("TaxRates") or [] if not deref(r, found).get("IsArchived")]
    work_types = [deref(w, found) for w in (lookup or {}).get("WorkTypes") or []]
    method = TAX_INCLUSIVE if args.get("tax_inclusive") else TAX_EXCLUSIVE
    price_group = job.get("PriceGroupId") or customer.get("PriceGroupId") or options.get("DefaultPriceGroupId")
    default_tax = (
        options.get("DefaultNoTaxTaxRateId") if customer.get("IsTaxExempt") else options.get("DefaultTaxRateId")
    )
    quote_id = new_id()
    lines: list[dict[str, Any]] = []
    for order, item in enumerate(args["line_items"], start=1):
        kind = item.get("type") or "misc"
        quantity = float(item["quantity"])
        extra: dict[str, Any] = {}
        if kind == "time":
            name = str(item.get("billing_rate") or "")
            work = next(
                (
                    w
                    for w in work_types
                    if name and name.lower() in (str(w.get("Name")).lower(), str(w.get("Description")).lower())
                ),
                None,
            ) or next((w for w in work_types if w.get("Id") == options.get("DefaultWorkTypeId")), None)
            if work is None:
                raise ToolError(f"No billing rate {name!r}.", ErrorCode.INVALID_INPUT)
            prices = [deref(p, found) for p in work.get("WorkTypeRates") or []]
            rate_price = next((p.get("UnitRate") for p in prices if p.get("PriceGroupId") == price_group), 0)
            unit_price = float(item["unit_price"]) if item.get("unit_price") is not None else float(rate_price or 0)
            unit_cost = float(item.get("unit_cost") if item.get("unit_cost") is not None else work.get("UnitCost") or 0)
            tax = _rate(rates, item.get("tax_rate"), work.get("TaxRateId") or default_tax)
            description = str(item.get("description") or work.get("Description") or work.get("Name") or "")
            extra = {"CostType": LABOUR, "WorkTypeId": work.get("Id")}
        else:
            if item.get("unit_price") is None or not item.get("description"):
                raise ToolError("A misc line needs description and unit_price.", ErrorCode.INVALID_INPUT)
            unit_price, unit_cost = float(item["unit_price"]), float(item.get("unit_cost") or 0)
            tax = _rate(rates, item.get("tax_rate"), default_tax)
            description = str(item["description"])
            extra = {"CostType": MISC}
        rate = float(tax.get("Rate") or 0)
        lines.append(
            {
                "Id": new_id(),
                "EstimateId": quote_id,
                **extra,
                "Description": description,
                "Quantity": quantity,
                "UnitPrice": unit_price,
                "UnitCost": unit_cost,
                "TaxRatePercentage": rate,
                "TaxRateDescription": tax.get("Description"),
                "SortOrder": order,
                "TenantId": EMPTY_ID,
                **line_amounts(quantity, unit_price, unit_cost, rate, method),
            }
        )
    taxes = tax_rows(lines, method, bool(options.get("CalcaulteTaxOnLineItems")))
    sums = totals(lines, taxes, method)
    today = await api.today()
    expiry = args.get("expiry_date")
    expiry_day = app_date(days_after(today, int(options.get("EstimateDefaultExpiryDays") or 30)))
    text = str(args.get("description") or job.get("Description") or "").strip()
    quote: dict[str, Any] = {
        "Id": quote_id,
        "EstimateNumber": "New",
        "EstimateSequence": 0,
        "EstimateVersion": 0,
        "CustomerId": customer.get("Id"),
        "JobId": job.get("Id"),
        "CustomerRef": args.get("reference") or job.get("CustomerRef"),
        "Description": text or None,
        "FormattedDescription": html_text(text) if text else None,
        "EstimateDate": app_date(today),
        "ExpiryDate": f"{expiry.replace('-', '/')} 00:00:00" if expiry else expiry_day,
        "Status": 1,
        "PriceGroupId": price_group,
        "DocumentFormatId": customer.get("DocumentFormatId") or options.get("DefaultDocumentFormatId"),
        "TaxCalculationMethodId": method,
        "IsTaxExempt": bool(customer.get("IsTaxExempt")),
        "IsSentToCustomer": False,
        "HasSignature": False,
        "AutomaticReminderEnabled": False,
        "SiteSMSReminderEnabled": False,
        "CustomerSMSReminderEnabled": False,
        "NotesVisibleToCustomers": False,
        "TenantId": EMPTY_ID,
        **sums,
        **await api.created(),
    }
    tax_entities = [
        entity(
            "EstimateTaxTotal", "EstimateTaxTotals", {"Id": new_id(), "EstimateId": quote_id, "TenantId": EMPTY_ID, **t}
        )
        for t in taxes
    ]
    saved = await api.save(
        [
            entity("Estimate", "Estimates", quote),
            *(entity("EstimateLine", "EstimateLines", line) for line in lines),
            *tax_entities,
        ]
    )
    stored = next((e for e in saved if e.get("Id") == quote_id), {})
    return {
        "quote_id": quote_id,
        "number": stored.get("EstimateNumber"),
        "status": "draft",
        "customer": customer.get("CustomerName"),
        "job_id": job.get("Id"),
        "lines": [
            {
                "description": line["Description"],
                "quantity": line["Quantity"],
                "unit_price": line["UnitPrice"],
                "amount": line["Amount"],
            }
            for line in lines
        ],
        "subtotal": sums["SubTotal"],
        "tax": sums["Tax"],
        "total": sums["Total"],
        "quote_date": iso_date(quote["EstimateDate"]),
        "expiry_date": iso_date(quote["ExpiryDate"]),
    }
