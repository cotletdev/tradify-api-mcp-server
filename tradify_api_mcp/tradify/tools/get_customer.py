"""Get customer: one customer with sites, notes and their latest jobs, quotes and invoices
(Customer/GetCustomerDetailData)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tradify_api_mcp.core.tools import tool
from tradify_api_mcp.tradify.tools._api import Api, iso_date, money, slug
from tradify_api_mcp.tradify.tools._invoices import entity_row as invoice_row
from tradify_api_mcp.tradify.tools._jobs import child, customer_detail, entity_row, job_statuses
from tradify_api_mcp.tradify.tools._quotes import quote_status
from tradify_api_mcp.tradify.tools.list_customers import customer_row

if TYPE_CHECKING:
    from tradify_api_mcp.core.context import ToolContext

LATEST = 25

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "customer_id": {"type": "string", "minLength": 1, "description": "Customer ID from list_customers."}
    },
    "required": ["customer_id"],
    "additionalProperties": False,
}

EXAMPLE_RESPONSE: dict[str, Any] = {
    "customer_id": "7801cbcd-8d5b-4506-afaa-011550798969",
    "name": "Riverside Dental Clinic",
    "contact": "Dana Price",
    "email": "office@example.com",
    "phone": "5550100142",
    "mobile": None,
    "address": "1200 Main St, Kansas City, MO 64105",
    "sites": [],
    "notes": [],
    "jobs": [
        {
            "job_id": "d3bd2e39-af25-4cda-9daf-d9f758f8f0e5",
            "number": "JB00001",
            "status": "to_invoice",
            "description": "Replace leaking water heater in staff kitchen",
        }
    ],
    "job_count": 1,
    "quotes": [
        {"quote_id": "89d70250-7c33-43f9-8311-966f32cd9559", "number": "QT00001", "status": "accepted", "total": 1219.0}
    ],
    "quote_count": 1,
    "invoices": [
        {
            "invoice_id": "558f2199-6ca6-489e-bfdf-d4d11cd878e3",
            "number": "IV00001",
            "status": "approved",
            "total": 609.5,
            "due": 159.5,
        }
    ],
    "invoice_count": 1,
    "balance_due": 159.5,
}


@tool(
    name="get_customer",
    title="Get customer",
    access="read",
    description="Customer profile with sites, notes, latest jobs, quotes and invoices, and the balance due.",
    details=(
        "Returns one customer: contact, email, phone, address, sites and notes, plus the latest 25 jobs, quotes and "
        "invoices with their totals (job_count, quote_count and invoice_count give the full numbers; list_jobs, "
        "list_quotes and list_invoices page through more). balance_due adds up what is due on the approved "
        "invoices returned."
    ),
    input_schema=INPUT_SCHEMA,
    route="GET /customers/{customer_id}",
    example_response=EXAMPLE_RESPONSE,
)
async def get_customer(ctx: ToolContext, args: dict[str, Any]) -> Any:
    api = Api(ctx)
    customer, body, found = await customer_detail(api, str(args["customer_id"]), size=LATEST)
    today = await api.today()
    statuses = {int(s["Id"]): slug(s.get("Description")) for s in await job_statuses(api)}
    jobs, job_count = child(body, found, "Jobs")
    quotes, quote_count = child(body, found, "Estimates")
    invoices, invoice_count = child(body, found, "Invoices")
    notes = child(body, found, "CustomerNotes")[0]
    job_rows = [entity_row(j, found, statuses) for j in jobs]
    invoice_rows = [invoice_row(i, found, today) for i in invoices]
    return {
        **customer_row(customer, found),
        "notes": [
            {"note": n.get("Note"), "created_on": iso_date(n.get("CreatedOn")), "by": n.get("CreatedBy")} for n in notes
        ],
        "jobs": [{k: row[k] for k in ("job_id", "number", "status", "description")} for row in job_rows],
        "job_count": job_count,
        "quotes": [
            {
                "quote_id": q.get("Id"),
                "number": q.get("EstimateNumber"),
                "status": quote_status(int(q.get("Status") or 0), q.get("ExpiryDate"), today),
                "total": money(q.get("Total")),
            }
            for q in quotes
        ],
        "quote_count": quote_count,
        "invoices": [{k: r[k] for k in ("invoice_id", "number", "status", "total", "due")} for r in invoice_rows],
        "invoice_count": invoice_count,
        "balance_due": round(sum(r["due"] for r in invoice_rows if r["status"] in ("approved", "overdue")), 2),
    }
