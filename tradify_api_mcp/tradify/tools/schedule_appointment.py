"""Schedule appointment: ScheduleItem (+ JobStaffMember, + the job's status) through SaveChanges, then the
optional customer email (Schedule/CustomerAppointmentNotification), as the Scheduler does."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tradify_api_mcp.core.errors import ErrorCode, ToolError
from tradify_api_mcp.core.tools import tool
from tradify_api_mcp.tradify.tools._api import (
    EMPTY_ID,
    MODIFIED,
    Api,
    app_time,
    deref,
    entity,
    new_id,
    objects,
    own,
    slug,
)
from tradify_api_mcp.tradify.tools._jobs import job_detail

if TYPE_CHECKING:
    from tradify_api_mcp.core.context import ToolContext

SCHEDULED, ACCEPTED, CREATE_MAIL = 3, 1, 1

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "job_id": {"type": "string", "minLength": 1, "description": "Job ID from list_jobs."},
        "start": {"type": "string", "format": "date-time", "description": "ISO 8601; without a zone, company time."},
        "end": {"type": "string", "format": "date-time", "description": "ISO 8601; without a zone, company time."},
        "staff": {
            "type": "array",
            "maxItems": 20,
            "items": {"type": "string"},
            "description": "Staff member names, one appointment each. Default: you.",
        },
        "notes": {"type": "string", "maxLength": 4000, "description": "Notes for the crew."},
        "email_customer": {"type": "boolean", "default": False, "description": "Email the customer a confirmation."},
        "customer_message": {"type": "string", "maxLength": 2000, "description": "Extra text in that email."},
    },
    "required": ["job_id", "start", "end"],
    "additionalProperties": False,
}

EXAMPLE_RESPONSE: dict[str, Any] = {
    "appointment_ids": ["7d1e2f3a-4b5c-4d6e-8f9a-0b1c2d3e4f5a"],
    "job_id": "42183ba9-17fa-4fe0-a585-216eb4b6b0e6",
    "job": "JB00002",
    "staff": ["Sam Carter"],
    "start": "2026-10-28T13:00:00-05:00",
    "end": "2026-10-28T15:00:00-05:00",
    "customer_emailed": False,
    "job_status": "scheduled",
}


@tool(
    name="schedule_appointment",
    title="Schedule appointment",
    access="write",
    confirm=True,
    description="Book a job appointment on the Scheduler for staff, optionally emailing the customer a confirmation.",
    details=(
        "Books the job on the Scheduler from start to end for each staff member named (by full name; default the "
        "signed-in user), as the Scheduler does. Each staff member gets Tradify's \"You've been scheduled\" "
        "notice, and an Unassigned or Assigned job becomes Scheduled. email_customer also sends the customer the "
        "appointment confirmation email, with customer_message in it. By default you confirm each call, and you "
        "can switch that off for this tool."
    ),
    input_schema=INPUT_SCHEMA,
    route="POST /jobs/{job_id}/appointments",
    example_response=EXAMPLE_RESPONSE,
)
async def schedule_appointment(ctx: ToolContext, args: dict[str, Any]) -> Any:
    api = Api(ctx)
    start, end = await api.local(str(args["start"])), await api.local(str(args["end"]))
    if end <= start:
        raise ToolError("end must be after start.", ErrorCode.INVALID_INPUT)
    job, body, found = await job_detail(api, str(args["job_id"]))
    job_id = str(job.get("Id"))
    lookup = await api.get("Schedule/GetSchedulerLookupData", {"jobId": job_id})
    lookup_objects = objects(lookup)
    people = [deref(s, lookup_objects) for s in (lookup or {}).get("StaffMembers") or []]
    people = [p for p in people if not p.get("IsArchived")]
    me = await api.staff()
    wanted = [name.strip() for name in args.get("staff") or [] if name.strip()] or [str(me.get("FullName"))]
    chosen = []
    for name in wanted:
        person = next((p for p in people if str(p.get("FullName")).lower() == name.lower()), None)
        if person is None:
            known = ", ".join(str(p.get("FullName")) for p in people)
            raise ToolError(f"No staff member {name!r}. Staff: {known}.", ErrorCode.INVALID_INPUT)
        chosen.append(person)
    children = deref(body.get("ChildData") or {}, found)
    on_job = {deref(m, found).get("StaffMemberId") for m in children.get("JobStaffMembers") or []}
    created = await api.created()
    email = bool(args.get("email_customer"))
    entities: list[dict[str, Any]] = []
    items = []
    for person in chosen:
        item = {
            "Id": new_id(),
            "JobId": job_id,
            "StaffMemberId": person.get("Id"),
            "StartTime": app_time(start),
            "EndTime": app_time(end),
            "Status": ACCEPTED,
            "IsOwner": True,
            "Visible": True,
            "Notes": args.get("notes"),
            "CustomerEmailNotified": email,
            "SiteEmailNotified": False,
            "CustomerSMSNotified": False,
            "SiteSMSNotified": False,
            "CustomerSMSEnabled": False,
            "SiteSMSEnabled": False,
            "LastModifiedById": me.get("Id"),
            "TenantId": EMPTY_ID,
            "CreatedOn": created["CreatedOn"],
            "CreatedBy": me.get("UserName") or me.get("Email"),
        }
        items.append(item)
        entities.append(entity("ScheduleItem", "ScheduleItems", item))
        if person.get("Id") not in on_job:
            link = {"Id": new_id(), "JobId": job_id, "StaffMemberId": person.get("Id"), "TenantId": EMPTY_ID}
            entities.append(entity("JobStaffMember", "JobStaffMembers", {**link, "IsNew": True}))
            on_job.add(person.get("Id"))
    status = int(job.get("JobStatusId") or 0)
    if status < SCHEDULED:
        fields = own(job)
        fields["JobStatusId"] = SCHEDULED
        entities.append(entity("Job", "Jobs", fields, MODIFIED, {"JobStatusId": status}))
        status = SCHEDULED
    await api.save(entities)
    if email:
        # One confirmation per booking: the customer gets the job's time, not one mail per staff member.
        await api.post(
            "Schedule/CustomerAppointmentNotification",
            {
                "scheduleItemId": items[0]["Id"],
                "optionalMessage": args.get("customer_message") or "",
                "customerReminderEmailType": CREATE_MAIL,
                "emailCustomer": True,
                "emailSite": False,
                "timeChanged": False,
                "staffMemberChanged": False,
            },
        )
    status_name = (
        "scheduled" if status == SCHEDULED else slug(deref(job.get("JobStatus") or {}, found).get("Description"))
    )
    return {
        "appointment_ids": [item["Id"] for item in items],
        "job_id": job_id,
        "job": job.get("JobNumber"),
        "staff": [p.get("FullName") for p in chosen],
        "start": await api.iso_moment(app_time(start)),
        "end": await api.iso_moment(app_time(end)),
        "customer_emailed": email,
        "job_status": status_name,
    }
