"""List quotes: the Quotes list (EstimateSummary/GetEstimates), newest quote date first."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tradify_api_mcp.core.helpers import limit, page_cursor
from tradify_api_mcp.core.tools import tool
from tradify_api_mcp.tradify.tools._api import Api, paged
from tradify_api_mcp.tradify.tools._quotes import quote_status

if TYPE_CHECKING:
    from tradify_api_mcp.core.context import ToolContext

# EstimateListFilter of the bundle; expired is awaiting acceptance past its expiry date.
LIST_FILTERS = {
    "draft": 0,
    "awaiting_acceptance": 1,
    "expired": 1,
    "accepted": 2,
    "cancelled": 3,
    "declined": 6,
    "all": 4,
}

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": list(LIST_FILTERS),
            "default": "awaiting_acceptance",
            "description": "awaiting_acceptance (default), draft, accepted, expired, cancelled, declined or all.",
        },
        "since": {"type": "string", "format": "date", "description": "Only quotes dated on or after this day."},
        "search": {"type": "string", "description": "Matches number, reference or customer."},
        "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50},
        "cursor": {"type": "string", "description": "next_cursor from the previous call."},
    },
    "required": [],
    "additionalProperties": False,
}

EXAMPLE_RESPONSE: dict[str, Any] = {
    "quotes": [
        {
            "quote_id": "89d70250-7c33-43f9-8311-966f32cd9559",
            "number": "QT00001",
            "customer_id": "7801cbcd-8d5b-4506-afaa-011550798969",
            "customer": "Riverside Dental Clinic",
            "job_id": "d3bd2e39-af25-4cda-9daf-d9f758f8f0e5",
            "job": "JB00001",
            "reference": "RD-1042",
            "total": 1219.0,
            "quote_date": "2026-10-23",
            "expiry_date": "2026-11-22",
            "accepted_on": "2026-10-23",
            "status": "accepted",
        }
    ],
    "next_cursor": None,
}


@tool(
    name="list_quotes",
    title="List quotes",
    access="read",
    description="Quotes with customer, total, quote date, expiry date and status.",
    details=(
        "Lists quotes, newest quote date first, with customer, linked job, total (with tax), quote, expiry and "
        "accepted dates and status. By default the quotes awaiting acceptance; expired is the ones awaiting "
        "acceptance past their expiry date. since keeps quotes dated on or after that day, so use status accepted "
        "with since to find what was won in a period. Pass next_cursor back as cursor."
    ),
    input_schema=INPUT_SCHEMA,
    route="GET /quotes",
    example_response=EXAMPLE_RESPONSE,
)
async def list_quotes(ctx: ToolContext, args: dict[str, Any]) -> Any:
    api = Api(ctx)
    size = limit(args, 50, 100)
    page = page_cursor(args.get("cursor"))
    status = str(args.get("status") or "awaiting_acceptance")
    since = str(args.get("since") or "")
    today = await api.today()
    body = await api.post(
        "EstimateSummary/GetEstimates",
        paged(
            page, size, "estimateDate", search=str(args.get("search") or ""), estimateListFilter=LIST_FILTERS[status]
        ),
    )
    rows = (body or {}).get("data") or []
    total = int((body or {}).get("totalCount") or 0)
    quotes = []
    for row in rows:
        customer = row.get("customer") or {}
        job = row.get("job") or {}
        quote = {
            "quote_id": row.get("id"),
            "number": row.get("estimateNumber"),
            "customer_id": row.get("customerId") or customer.get("id"),
            "customer": customer.get("customerName"),
            "job_id": row.get("jobId"),
            "job": job.get("jobNumber"),
            "reference": row.get("customerRef"),
            "total": float(row.get("total") or 0),
            "quote_date": str(row.get("estimateDate") or "")[:10] or None,
            "expiry_date": str(row.get("expiryDate") or "")[:10] or None,
            "accepted_on": str(row.get("acceptedOn") or "")[:10] or None,
            "status": quote_status(int(row.get("status") or 0), row.get("expiryDate"), today),
        }
        quotes.append(quote)
    if status == "expired":
        quotes = [q for q in quotes if q["status"] == "expired"]
    more = page * size < total
    if since:
        more = more and all((q["quote_date"] or "") >= since for q in quotes)
        quotes = [q for q in quotes if (q["quote_date"] or "") >= since]
    return {"quotes": quotes, "next_cursor": str(page + 1) if more else None}
