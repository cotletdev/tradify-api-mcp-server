"""List invoices: the Invoices list (InvoiceSummary/GetInvoices), or one customer's (Customer/GetCustomerDetailData)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tradify_api_mcp.core.helpers import limit, page_cursor
from tradify_api_mcp.core.tools import tool
from tradify_api_mcp.tradify.tools._api import Api, paged
from tradify_api_mcp.tradify.tools._invoices import LIST_FILTERS, entity_row, summary_row
from tradify_api_mcp.tradify.tools._jobs import child, customer_detail

if TYPE_CHECKING:
    from tradify_api_mcp.core.context import ToolContext

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": list(LIST_FILTERS),
            "default": "approved",
            "description": "approved (sent, not fully paid; default), overdue, paid, draft, cancelled or all.",
        },
        "customer_id": {"type": "string", "description": "Only this customer's invoices (list_customers)."},
        "search": {"type": "string", "description": "Matches number, reference or customer."},
        "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50},
        "cursor": {"type": "string", "description": "next_cursor from the previous call."},
    },
    "required": [],
    "additionalProperties": False,
}

EXAMPLE_RESPONSE: dict[str, Any] = {
    "invoices": [
        {
            "invoice_id": "558f2199-6ca6-489e-bfdf-d4d11cd878e3",
            "number": "IV00001",
            "customer_id": "7801cbcd-8d5b-4506-afaa-011550798969",
            "customer": "Riverside Dental Clinic",
            "jobs": ["JB00001"],
            "invoice_date": "2026-10-23",
            "due_date": "2026-10-30",
            "total": 609.5,
            "paid": 300.0,
            "due": 309.5,
            "status": "approved",
        }
    ],
    "next_cursor": None,
}


@tool(
    name="list_invoices",
    title="List invoices",
    access="read",
    description="Invoices with customer, job, due date, total, amount paid and amount due.",
    details=(
        "Lists invoices, newest first, with customer, jobs, invoice and due dates, total, paid and due (total minus "
        "payments and credits). status approved (default) is every approved invoice not fully paid; overdue is "
        "the ones past their due date; paid, draft, cancelled and all as named. customer_id lists that customer's "
        "invoices, and status then filters the page you get. Pass next_cursor back as cursor."
    ),
    input_schema=INPUT_SCHEMA,
    route="GET /invoices",
    example_response=EXAMPLE_RESPONSE,
)
async def list_invoices(ctx: ToolContext, args: dict[str, Any]) -> Any:
    api = Api(ctx)
    size = limit(args, 50, 100)
    page = page_cursor(args.get("cursor"))
    status = str(args.get("status") or "approved")
    today = await api.today()
    if args.get("customer_id"):
        _, body, found = await customer_detail(api, str(args["customer_id"]), page, size)
        rows, total = child(body, found, "Invoices")
        invoices = [entity_row(r, found, today) for r in rows]
        if status == "approved":
            invoices = [i for i in invoices if i["status"] in ("approved", "overdue")]
        elif status != "all":
            invoices = [i for i in invoices if i["status"] == status]
        if search := str(args.get("search") or "").lower():
            invoices = [i for i in invoices if search in " ".join(str(v) for v in i.values()).lower()]
    else:
        body = await api.post(
            "InvoiceSummary/GetInvoices",
            paged(
                page, size, "createdOn", search=str(args.get("search") or ""), invoiceListFilter=LIST_FILTERS[status]
            ),
        )
        rows = (body or {}).get("data") or []
        total = int((body or {}).get("totalCount") or 0)
        invoices = [summary_row(r, today) for r in rows]
    return {"invoices": invoices, "next_cursor": str(page + 1) if page * size < total else None}
