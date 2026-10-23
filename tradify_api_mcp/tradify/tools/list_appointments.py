"""List appointments: the Scheduler's appointments between two days (Schedule/GetAppointments)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

from tradify_api_mcp.core.errors import ErrorCode, ToolError
from tradify_api_mcp.core.tools import tool
from tradify_api_mcp.tradify.tools._api import APPOINTMENT_STATUSES, Api, app_date, deref, objects

if TYPE_CHECKING:
    from tradify_api_mcp.core.context import ToolContext

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "from": {"type": "string", "format": "date", "description": "First day."},
        "to": {"type": "string", "format": "date", "description": "Last day, up to 31 days after from."},
        "staff": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Only these staff members, by full name.",
        },
    },
    "required": ["from", "to"],
    "additionalProperties": False,
}

EXAMPLE_RESPONSE: dict[str, Any] = {
    "appointments": [
        {
            "appointment_id": "3f6a914a-cd35-479f-855f-9de005e44cb2",
            "job_id": "d3bd2e39-af25-4cda-9daf-d9f758f8f0e5",
            "job": "JB00001",
            "customer": "Riverside Dental Clinic",
            "staff": ["Sam Carter"],
            "start": "2026-10-27T09:00:00-05:00",
            "end": "2026-10-27T12:00:00-05:00",
            "notes": "Bring 50 gal unit, shut-off valve at rear",
            "status": "accepted",
        }
    ]
}


@tool(
    name="list_appointments",
    title="List appointments",
    access="read",
    description="Scheduler appointments in a date range, with staff, job, times and notes.",
    details=(
        "Returns the Scheduler's job appointments that fall between from and to (both days included, at most 31 "
        "days), each with its job, customer, staff member, start and end (ISO 8601 with the company's UTC offset), "
        "notes and status (accepted, unconfirmed, declined, cancelled). staff keeps only those people, by full name."
    ),
    input_schema=INPUT_SCHEMA,
    route="GET /appointments",
    example_response=EXAMPLE_RESPONSE,
)
async def list_appointments(ctx: ToolContext, args: dict[str, Any]) -> Any:
    try:
        first, last = date.fromisoformat(args["from"]), date.fromisoformat(args["to"])
    except ValueError as exc:
        raise ToolError("from and to must be dates (YYYY-MM-DD).", ErrorCode.INVALID_INPUT) from exc
    if last < first or (last - first).days > 31:
        raise ToolError("to must be on or after from, at most 31 days later.", ErrorCode.INVALID_INPUT)
    api = Api(ctx)
    body = await api.post(
        "Schedule/GetAppointments", {"from": app_date(first), "to": app_date(last + timedelta(days=1))}
    )
    found = objects(body)
    wanted = {name.strip().lower() for name in args.get("staff") or []}
    appointments = []
    for item in [deref(i, found) for i in (body or {}).get("ScheduleItems") or []]:
        staff = deref(item.get("StaffMember") or {}, found).get("FullName")
        if wanted and str(staff or "").lower() not in wanted:
            continue
        job = deref(item.get("Job") or {}, found)
        customer = deref(job.get("Customer") or {}, found)
        appointments.append(
            {
                "appointment_id": item.get("Id"),
                "job_id": item.get("JobId"),
                "job": job.get("JobNumber"),
                "customer": customer.get("CustomerName"),
                "staff": [staff] if staff else [],
                "start": await api.iso_moment(item.get("StartTime")),
                "end": await api.iso_moment(item.get("EndTime")),
                "notes": item.get("Notes"),
                "status": APPOINTMENT_STATUSES.get(int(item.get("Status") or 0), ""),
            }
        )
    appointments.sort(key=lambda a: str(a["start"]))
    return {"appointments": appointments}
