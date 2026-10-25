"""Log time: a new TimesheetEntry through SaveChanges, as the "New Timesheet Entry" dialog sends it."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from tradify_api_mcp.core.errors import ErrorCode, ToolError
from tradify_api_mcp.core.tools import tool
from tradify_api_mcp.tradify.tools._api import EMPTY_ID, Api, deref, entity, new_id, objects
from tradify_api_mcp.tradify.tools._jobs import job_detail
from tradify_api_mcp.tradify.tools._timesheets import entry_times, staff_member, timesheets

if TYPE_CHECKING:
    from tradify_api_mcp.core.context import ToolContext

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "start": {"type": "string", "format": "date-time", "description": "Start, ISO 8601; no zone = company time."},
        "end": {"type": "string", "format": "date-time", "description": "Finish, the same day as start."},
        "job_id": {"type": "string", "description": "The job the time was spent on (list_jobs). Default: no job."},
        "staff": {"type": "string", "description": "Staff member's full name. Default: you."},
        "billing_rate": {
            "type": "string",
            "description": "Billing rate name (e.g. Standard Labour Rate). Default: the staff member's own rate.",
        },
        "notes": {"type": "string", "maxLength": 2000},
    },
    "required": ["start", "end"],
    "additionalProperties": False,
}

EXAMPLE_RESPONSE: dict[str, Any] = {
    "timesheet_id": "18d3f342-a27a-416d-a0f8-17ff8a0eea03",
    "staff": "Sam Carter",
    "job": "JB00002",
    "billing_rate": "Standard Labour Rate",
    "start": "2026-10-26T08:00:00-05:00",
    "end": "2026-10-26T10:30:00-05:00",
    "hours": 2.5,
    "status": "created",
}


@tool(
    name="log_time",
    title="Log time",
    access="write",
    description="Add a timesheet entry for a staff member, optionally on a job, with billing rate and notes.",
    details=(
        "Adds one entry to Timesheets from start to end (same day, at most 24 hours) for a staff member (default "
        "the signed-in user), on a job or on none, at a billing rate (default the staff member's own) with the "
        "staff member's cost rate, as the New Timesheet Entry dialog does. Time on a job shows in its costs, the "
        "job profitability report and can be invoiced. It reaches no one."
    ),
    input_schema=INPUT_SCHEMA,
    route="POST /timesheets",
    example_response=EXAMPLE_RESPONSE,
)
async def log_time(ctx: ToolContext, args: dict[str, Any]) -> Any:
    api = Api(ctx)
    start, end = await api.local(str(args["start"])), await api.local(str(args["end"]))
    if end <= start or end - start > timedelta(hours=24) or end.date() != start.date():
        raise ToolError("end must be after start, on the same day.", ErrorCode.INVALID_INPUT)
    body, found = await timesheets(api, start.date(), start.date())
    people = [deref(p, found) for p in body.get("StaffMembers") or []]
    name = str(args.get("staff") or "").strip() or str((await api.staff()).get("FullName") or "")
    person = staff_member(people, name)
    job: dict[str, Any] = {}
    if args.get("job_id"):
        job, _, _ = await job_detail(api, str(args["job_id"]))
    lookup = await api.get("Estimate/GetEstimateLookupData", {"customerId": job.get("CustomerId") or ""})
    lookup_found = objects(lookup)
    rates = [deref(w, lookup_found) for w in (lookup or {}).get("WorkTypes") or []]
    wanted = str(args.get("billing_rate") or "").strip().lower()
    default = person.get("WorkTypeId") or (await api.options()).get("DefaultWorkTypeId")
    work = next(
        (w for w in rates if wanted and wanted in (str(w.get("Name")).lower(), str(w.get("Description")).lower())),
        None,
    ) or (None if wanted else next((w for w in rates if w.get("Id") == default), None))
    if work is None:
        known = ", ".join(str(w.get("Name")) for w in rates if not w.get("IsArchived"))
        raise ToolError(f"No billing rate {args.get('billing_rate')!r}. Rates: {known}.", ErrorCode.INVALID_INPUT)
    fields: dict[str, Any] = {
        "Id": new_id(),
        **await api.created(),
        **entry_times(start, end),
        "Notes": str(args["notes"]) if args.get("notes") else None,
        "StaffMemberId": person.get("Id"),
        "JobId": job.get("Id"),
        "JobTaskId": None,
        "WorkTypeId": work.get("Id"),
        "StaffMemberUnitCost": float(person.get("UnitCost") or 0),
        "InvoiceId": None,
        "TenantId": EMPTY_ID,
    }
    await api.save([entity("TimesheetEntry", "TimesheetEntries", fields)])
    return {
        "timesheet_id": fields["Id"],
        "staff": person.get("FullName"),
        "job": job.get("JobNumber"),
        "billing_rate": work.get("Name"),
        "start": await api.iso_moment(fields["StartTime"]),
        "end": await api.iso_moment(fields["EndTime"]),
        "hours": round(fields["Duration"], 2),
        "status": "created",
    }
