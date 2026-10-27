"""Update job status: the Jobs list's bulk status change (Job/BulkUpdateJobStatus) for one job."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tradify_api_mcp.core.errors import ErrorCode, ToolError
from tradify_api_mcp.core.tools import tool
from tradify_api_mcp.tradify.tools._api import Api, slug
from tradify_api_mcp.tradify.tools._jobs import job_detail, job_statuses, status_ids

if TYPE_CHECKING:
    from tradify_api_mcp.core.context import ToolContext

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "job_id": {"type": "string", "minLength": 1, "description": "Job ID from list_jobs."},
        "status": {
            "type": "string",
            "minLength": 1,
            "description": (
                "unassigned, assigned, scheduled, in_progress, to_invoice, on_hold, complete, cancelled or the name "
                "of a custom status."
            ),
        },
    },
    "required": ["job_id", "status"],
    "additionalProperties": False,
}

EXAMPLE_RESPONSE: dict[str, Any] = {"job_id": "d3bd2e39-af25-4cda-9daf-d9f758f8f0e5", "status": "complete"}


@tool(
    name="update_job_status",
    title="Update job status",
    access="write",
    description="Set a status on a job, built-in or one of your custom statuses.",
    details=(
        "Sets a job's status, as Change Status on the Jobs list does: to_invoice, on_hold, complete, cancelled, "
        "the others of the built-in list, or the name of a custom status from Settings > Jobs > Job Statuses "
        "(spaces as underscores). It reaches no one, and one more call sets it back."
    ),
    input_schema=INPUT_SCHEMA,
    route="PATCH /jobs/{job_id}/status",
    example_response=EXAMPLE_RESPONSE,
)
async def update_job_status(ctx: ToolContext, args: dict[str, Any]) -> Any:
    api = Api(ctx)
    wanted = str(args["status"])
    if slug(wanted) in ("active", "all"):
        raise ToolError("status must be one job status, not active or all.", ErrorCode.INVALID_INPUT)
    statuses = await job_statuses(api)
    status_id = status_ids(statuses, wanted)[0]
    job_id = str(args["job_id"])
    answer = await api.post("Job/BulkUpdateJobStatus", {"jobIds": [job_id], "jobStatusId": status_id})
    answer = answer if isinstance(answer, dict) else {}
    if answer.get("FailedJobIds") or not answer.get("UpdatedCount"):
        # Tradify counts no update when the job already has this status: that is success.
        job, _, _ = await job_detail(api, job_id)
        if answer.get("FailedJobIds") or int(job.get("JobStatusId") or 0) != status_id:
            raise ToolError(
                "Tradify did not change this job's status; check the job_id (list_jobs).", ErrorCode.TARGET_ERROR
            )
    name = next(s.get("Description") for s in statuses if int(s["Id"]) == status_id)
    return {"job_id": job_id, "status": slug(name)}
