"""Get job: Job/GetJobDetailData with every child block (tasks, notes, appointments, costs, quotes, invoices)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tradify_api_mcp.core.tools import tool
from tradify_api_mcp.tradify.tools._api import APPOINTMENT_STATUSES, QUOTE_STATUSES, Api, deref, iso_date, money, slug
from tradify_api_mcp.tradify.tools._invoices import invoice_status
from tradify_api_mcp.tradify.tools._jobs import child, job_detail

if TYPE_CHECKING:
    from tradify_api_mcp.core.context import ToolContext

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"job_id": {"type": "string", "minLength": 1, "description": "Job ID from list_jobs."}},
    "required": ["job_id"],
    "additionalProperties": False,
}

EXAMPLE_RESPONSE: dict[str, Any] = {
    "job_id": "d3bd2e39-af25-4cda-9daf-d9f758f8f0e5",
    "number": "JB00001",
    "customer_id": "7801cbcd-8d5b-4506-afaa-011550798969",
    "customer": "Riverside Dental Clinic",
    "contact": "Riverside Dental Clinic",
    "phone": "5550100142",
    "site_address": "1200 Main St, Kansas City, MO 64105",
    "status": "to_invoice",
    "reference": "RD-1042",
    "description": "Replace leaking water heater in staff kitchen",
    "staff": ["Sam Carter"],
    "tasks": [],
    "notes": [],
    "appointments": [
        {
            "appointment_id": "3f6a914a-cd35-479f-855f-9de005e44cb2",
            "staff": ["Sam Carter"],
            "start": "2026-10-27T09:00:00-05:00",
            "end": "2026-10-27T12:00:00-05:00",
            "notes": "Bring 50 gal unit, shut-off valve at rear",
            "status": "accepted",
        }
    ],
    "costs": [],
    "quotes": [
        {"quote_id": "89d70250-7c33-43f9-8311-966f32cd9559", "number": "QT00001", "status": "accepted", "total": 1219.0}
    ],
    "invoices": [
        {
            "invoice_id": "558f2199-6ca6-489e-bfdf-d4d11cd878e3",
            "number": "IV00001",
            "status": "approved",
            "total": 609.5,
            "due": 309.5,
        }
    ],
}


@tool(
    name="get_job",
    title="Get job",
    access="read",
    description="Full job: description, site, tasks, notes, appointments, costs, linked quotes and invoices.",
    details=(
        "Returns one job: customer, contact, site address, status, reference and description, the staff on it, "
        "its tasks and notes, the Scheduler appointments (times with the company's UTC offset), the costs logged "
        "on it (products and misc costs) and the quotes and invoices linked to it. Read it before changing a job."
    ),
    input_schema=INPUT_SCHEMA,
    route="GET /jobs/{job_id}",
    example_response=EXAMPLE_RESPONSE,
)
async def get_job(ctx: ToolContext, args: dict[str, Any]) -> Any:
    api = Api(ctx)
    job, body, found = await job_detail(api, str(args["job_id"]))
    children = deref(body.get("ChildData") or {}, found)
    customer = deref(job.get("Customer") or {}, found)
    status = deref(job.get("JobStatus") or {}, found)

    def names(rows: list[Any]) -> list[str]:
        members = [deref(deref(r, found).get("StaffMember") or {}, found).get("FullName") for r in rows]
        return [str(name) for name in members if name]

    appointments = []
    for item in child(body, found, "ScheduleItems")[0]:
        staff = deref(item.get("StaffMember") or {}, found).get("FullName")
        appointments.append(
            {
                "appointment_id": item.get("Id"),
                "staff": [staff] if staff else [],
                "start": await api.iso_moment(item.get("StartTime")),
                "end": await api.iso_moment(item.get("EndTime")),
                "notes": item.get("Notes"),
                "status": APPOINTMENT_STATUSES.get(int(item.get("Status") or 0), ""),
            }
        )
    tasks = [deref(t, found) for t in children.get("JobTasks") or []]
    notes = child(body, found, "JobNotes")[0]
    costs = [deref(c, found) for c in [*(children.get("JobProducts") or []), *(children.get("JobMiscCosts") or [])]]
    return {
        "job_id": job.get("Id"),
        "number": job.get("JobNumber"),
        "customer_id": job.get("CustomerId"),
        "customer": customer.get("CustomerName"),
        "contact": job.get("JobContact"),
        "phone": job.get("JobContactPhoneNumber"),
        "site_address": job.get("SiteAddress"),
        "status": slug(status.get("Description")),
        "reference": job.get("CustomerRef"),
        "description": str(job.get("Description") or "").strip(),
        "staff": names(children.get("JobStaffMembers") or []),
        "tasks": [
            {
                "name": t.get("Name") or t.get("DisplayName") or t.get("Description"),
                "done": bool(t.get("IsCompleted") or t.get("IsComplete")),
            }
            for t in tasks
        ],
        "notes": [
            {"note": n.get("Note"), "created_on": iso_date(n.get("CreatedOn")), "by": n.get("CreatedBy")} for n in notes
        ],
        "appointments": appointments,
        "costs": [
            {"description": c.get("Description"), "quantity": c.get("Quantity"), "amount": money(c.get("Amount"))}
            for c in costs
        ],
        "quotes": [
            {
                "quote_id": q.get("Id"),
                "number": q.get("EstimateNumber"),
                "status": QUOTE_STATUSES.get(int(q.get("Status") or 0), ""),
                "total": money(q.get("Total")),
            }
            for q in child(body, found, "Estimates")[0]
        ],
        "invoices": [
            {
                "invoice_id": i.get("Id"),
                "number": i.get("InvoiceNumber"),
                "status": invoice_status(i, await api.today()),
                "total": money(i.get("Total")),
                "due": money(i.get("Due")),
            }
            for i in child(body, found, "Invoices")[0]
        ],
    }
