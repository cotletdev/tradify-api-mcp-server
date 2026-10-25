"""List timesheets: the Timesheets page's entries between two days (Timesheet/GetTimesheets)."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from tradify_api_mcp.core.errors import ErrorCode, ToolError
from tradify_api_mcp.core.tools import tool
from tradify_api_mcp.tradify.tools._api import Api, deref
from tradify_api_mcp.tradify.tools._timesheets import entry_row, timesheets

if TYPE_CHECKING:
    from tradify_api_mcp.core.context import ToolContext

MAX_DAYS = 62

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "from": {"type": "string", "format": "date", "description": "First day."},
        "to": {"type": "string", "format": "date", "description": "Last day, up to 62 days after from."},
        "staff": {"type": "string", "description": "Only this staff member, by full name."},
        "job_id": {"type": "string", "description": "Only time on this job (list_jobs)."},
    },
    "required": ["from", "to"],
    "additionalProperties": False,
}

EXAMPLE_RESPONSE: dict[str, Any] = {
    "timesheets": [
        {
            "timesheet_id": "17e94a82-c684-4781-ba18-c5ab3eeb6a12",
            "date": "2026-10-23",
            "staff": "Sam Carter",
            "job_id": "42183ba9-17fa-4fe0-a585-216eb4b6b0e6",
            "job": "JB00002",
            "customer": "Maple Street Bakery",
            "billing_rate": "Standard Labour Rate",
            "billable": True,
            "start": "2026-10-23T08:00:00-05:00",
            "end": "2026-10-23T10:30:00-05:00",
            "hours": 2.5,
            "notes": "Removed old grease trap, measured for new unit",
            "invoiced": False,
        }
    ],
    "total_hours": 2.5,
}


@tool(
    name="list_timesheets",
    title="List timesheets",
    access="read",
    description="Timesheet entries in a date range: staff, job, customer, billing rate, hours, notes, invoiced.",
    details=(
        "Returns the time entries between from and to (both days included, at most 62 days), oldest first, each "
        "with staff member, job and customer (none for time off a job), billing rate and whether it is billable, "
        "start and end (ISO 8601 with the company's UTC offset), hours, notes and whether it is on an invoice. "
        "staff and job_id narrow it. total_hours sums the entries returned."
    ),
    input_schema=INPUT_SCHEMA,
    route="GET /timesheets",
    example_response=EXAMPLE_RESPONSE,
)
async def list_timesheets(ctx: ToolContext, args: dict[str, Any]) -> Any:
    try:
        first, last = date.fromisoformat(str(args["from"])), date.fromisoformat(str(args["to"]))
    except ValueError as exc:
        raise ToolError("from and to must be dates like 2026-10-31.", ErrorCode.INVALID_INPUT) from exc
    if last < first or (last - first).days > MAX_DAYS:
        raise ToolError("to must be on or after from, at most 62 days later.", ErrorCode.INVALID_INPUT)
    api = Api(ctx)
    body, found = await timesheets(api, first, last)
    entries = [deref(e, found) for e in body.get("TimesheetEntries") or []]
    entries.sort(key=lambda e: str(e.get("StartTime") or ""))
    rows = [await entry_row(api, e, found) for e in entries]
    if staff := str(args.get("staff") or "").strip().lower():
        rows = [r for r in rows if str(r["staff"] or "").lower() == staff]
    if job_id := args.get("job_id"):
        rows = [r for r in rows if r["job_id"] == job_id]
    return {"timesheets": rows, "total_hours": round(sum(r["hours"] for r in rows), 2)}
