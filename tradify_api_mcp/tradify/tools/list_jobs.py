"""List jobs: the Jobs list (JobSummary/GetJobs), or one customer's jobs (Customer/GetCustomerDetailData)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tradify_api_mcp.core.helpers import limit, page_cursor
from tradify_api_mcp.core.tools import tool
from tradify_api_mcp.tradify.tools._api import Api, paged, slug
from tradify_api_mcp.tradify.tools._jobs import (
    child,
    customer_detail,
    entity_row,
    job_statuses,
    status_ids,
    summary_row,
)

if TYPE_CHECKING:
    from tradify_api_mcp.core.context import ToolContext

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "description": (
                "active (default), all, unassigned, assigned, scheduled, in_progress, to_invoice, on_hold, complete, "
                "cancelled or the name of a custom status."
            ),
        },
        "customer_id": {"type": "string", "description": "Only this customer's jobs (list_customers)."},
        "search": {"type": "string", "description": "Matches job number, customer or reference."},
        "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50},
        "cursor": {"type": "string", "description": "next_cursor from the previous call."},
    },
    "required": [],
    "additionalProperties": False,
}

EXAMPLE_RESPONSE: dict[str, Any] = {
    "jobs": [
        {
            "job_id": "d3bd2e39-af25-4cda-9daf-d9f758f8f0e5",
            "number": "JB00001",
            "customer_id": "7801cbcd-8d5b-4506-afaa-011550798969",
            "customer": "Riverside Dental Clinic",
            "site_address": "1200 Main St, Kansas City, MO 64105",
            "status": "to_invoice",
            "staff": ["Sam Carter"],
            "description": "Replace leaking water heater in staff kitchen",
            "reference": "RD-1042",
        }
    ],
    "next_cursor": None,
}


@tool(
    name="list_jobs",
    title="List jobs",
    access="read",
    description="Jobs with number, customer, site address, status and assigned staff.",
    details=(
        "Lists jobs, newest number first. By default only active jobs (every status marked active, built-in or "
        "custom); status all, a built-in status or the name of a custom status narrows it. customer_id lists that "
        "customer's jobs, and status then filters the page you get. Pass next_cursor back as cursor."
    ),
    input_schema=INPUT_SCHEMA,
    route="GET /jobs",
    example_response=EXAMPLE_RESPONSE,
)
async def list_jobs(ctx: ToolContext, args: dict[str, Any]) -> Any:
    api = Api(ctx)
    size = limit(args, 50, 100)
    page = page_cursor(args.get("cursor"))
    statuses = await job_statuses(api)
    ids = status_ids(statuses, str(args.get("status") or "active"))
    if args.get("customer_id"):
        _, body, found = await customer_detail(api, str(args["customer_id"]), page, size)
        rows, total = child(body, found, "Jobs")
        names = {int(s["Id"]): slug(s.get("Description")) for s in statuses}
        search = str(args.get("search") or "").lower()
        jobs = [entity_row(r, found, names) for r in rows if int(r.get("JobStatusId") or 0) in ids]
        if search:
            jobs = [j for j in jobs if search in " ".join(str(v) for v in j.values()).lower()]
    else:
        body = await api.post(
            "JobSummary/GetJobs",
            paged(page, size, "jobNumber", search=str(args.get("search") or ""), includeJobStatusIds=ids),
        )
        rows = (body or {}).get("data") or []
        total = int((body or {}).get("totalCount") or 0)
        jobs = [summary_row(r) for r in rows]
    return {"jobs": jobs, "next_cursor": str(page + 1) if page * size < total else None}
