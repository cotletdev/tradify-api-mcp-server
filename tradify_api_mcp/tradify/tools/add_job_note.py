"""Add job note: a JobNote entity through SaveChanges, as the job's Notes tab "New Note" dialog saves it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tradify_api_mcp.core.tools import tool
from tradify_api_mcp.tradify.tools._api import EMPTY_ID, Api, entity, iso_date, new_id
from tradify_api_mcp.tradify.tools._jobs import job_detail

if TYPE_CHECKING:
    from tradify_api_mcp.core.context import ToolContext

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "job_id": {"type": "string", "minLength": 1, "description": "Job ID from list_jobs."},
        "note": {"type": "string", "minLength": 1, "maxLength": 4000, "description": "Plain text."},
    },
    "required": ["job_id", "note"],
    "additionalProperties": False,
}

EXAMPLE_RESPONSE: dict[str, Any] = {
    "note_id": "9d772457-b64e-474d-959e-d434838db27f",
    "job": "JB00003",
    "note": "Customer asked to use the side gate.",
    "created_on": "2026-10-25",
    "by": "Sam Carter",
    "status": "created",
}


@tool(
    name="add_job_note",
    title="Add job note",
    access="write",
    description="Add a text note to a job's Notes tab.",
    details=(
        "Adds a plain-text note to the job, signed with the signed-in user's name and today's date, as the Notes "
        "tab's New Note does. No staff member is notified and it reaches no one. get_job lists the notes."
    ),
    input_schema=INPUT_SCHEMA,
    route="POST /jobs/{job_id}/notes",
    example_response=EXAMPLE_RESPONSE,
)
async def add_job_note(ctx: ToolContext, args: dict[str, Any]) -> Any:
    api = Api(ctx)
    job, _, _ = await job_detail(api, str(args["job_id"]))
    created = await api.created()
    fields = {
        "Id": new_id(),
        **created,
        "Note": str(args["note"]).strip(),
        "NotifiedStaffMembers": "",
        "JobId": job.get("Id"),
        "TenantId": EMPTY_ID,
        "ReferenceId": None,
    }
    await api.save([entity("JobNote", "JobNotes", fields)])
    return {
        "note_id": fields["Id"],
        "job": job.get("JobNumber"),
        "note": fields["Note"],
        "created_on": iso_date(created["CreatedOn"]),
        "by": created["CreatedBy"],
        "status": "created",
    }
