"""Timesheets: the week view's call (Timesheet/GetTimesheets), its staff list and entry rows."""

from __future__ import annotations

from typing import Any

from tradify_api_mcp.core.errors import ErrorCode, ToolError
from tradify_api_mcp.tradify.tools._api import Api, app_time, deref, objects, parse_local


async def timesheets(api: Api, first: Any, last: Any) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """`Timesheet/GetTimesheets` from the start of day `first` to the end of day `last`: (answer, objects).

    The answer carries `TimesheetEntries` and every staff member with their default billing rate and cost."""
    period = {"from": f"{first:%Y/%m/%d} 00:00:00", "to": f"{last:%Y/%m/%d} 23:59:59"}
    body = await api.post("Timesheet/GetTimesheets", period)
    return body or {}, objects(body)


def staff_member(people: list[dict[str, Any]], name: str) -> dict[str, Any]:
    match = next((p for p in people if str(p.get("FullName") or "").lower() == name.lower()), None)
    if match is None:
        known = ", ".join(str(p.get("FullName")) for p in people if p.get("FullName") and not p.get("IsArchived"))
        raise ToolError(f"No staff member {name!r}. Staff: {known}.", ErrorCode.INVALID_INPUT)
    return match


async def entry_row(api: Api, entry: dict[str, Any], found: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """A TimesheetEntry entity (PascalCase, refs) as a row."""
    staff = deref(entry.get("StaffMember") or {}, found)
    job = deref(entry.get("Job") or {}, found)
    customer = deref(job.get("Customer") or {}, found)
    work = deref(entry.get("WorkType") or {}, found)
    start = parse_local(entry.get("StartTime"))
    return {
        "timesheet_id": entry.get("Id"),
        "date": start.date().isoformat() if start else None,
        "staff": staff.get("FullName"),
        "job_id": entry.get("JobId"),
        "job": job.get("JobNumber"),
        "customer": customer.get("CustomerName"),
        "billing_rate": work.get("Name"),
        "billable": not work.get("IsNonChargeable") if work else None,
        "start": await api.iso_moment(entry.get("StartTime")),
        "end": await api.iso_moment(entry.get("EndTime")),
        "hours": round(float(entry.get("Duration") or 0), 2),
        "notes": entry.get("Notes"),
        "invoiced": bool(entry.get("InvoiceId")),
    }


def entry_times(start: Any, end: Any) -> dict[str, Any]:
    """StartTime, EndTime and Duration (hours) of a new entry, as the entry dialog fills them."""
    return {
        "StartTime": app_time(start),
        "EndTime": app_time(end),
        "Duration": round((end - start).total_seconds() / 3600, 4),
    }
