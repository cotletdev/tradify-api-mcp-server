"""Jobs and customers: status lookup, list rows, the job and customer detail calls."""

from __future__ import annotations

from typing import Any

from tradify_api_mcp.core.errors import ErrorCode, ToolError
from tradify_api_mcp.tradify.tools._api import Api, child_block, deref, objects, slug

JOB_BLOCKS = (
    "jobNotesQueryParams",
    "formsQueryParams",
    "scheduleItemsQueryParams",
    "invoicesQueryParams",
    "estimatesQueryParams",
    "purchaseOrdersQueryParams",
    "supplierInvoicesQueryParams",
    "jobServiceReportsQueryParams",
)
CUSTOMER_BLOCKS = (
    "customerLocationsQueryParams",
    "customerNotesQueryParams",
    "jobsQueryParams",
    "recurringJobsQueryParams",
    "serviceRemindersQueryParams",
    "invoicesQueryParams",
    "recurringInvoicesQueryParams",
    "estimatesQueryParams",
)


async def job_statuses(api: Api) -> list[dict[str, Any]]:
    """Job statuses of the company (built-in and custom): Id, Description, IsActiveStatus."""
    body = await api.get("Job/GetJobListLookupData")
    found = objects(body)
    return [deref(s, found) for s in (body or {}).get("JobStatuses") or []]


def status_ids(statuses: list[dict[str, Any]], wanted: str) -> list[int]:
    """Status ids for a tool status: active, all, or a status name (to_invoice, on_hold, a custom one)."""
    if wanted == "all":
        return [int(s["Id"]) for s in statuses]
    if wanted == "active":
        return [int(s["Id"]) for s in statuses if s.get("IsActiveStatus")]
    ids = [int(s["Id"]) for s in statuses if slug(s.get("Description")) == slug(wanted)]
    if not ids:
        names = ", ".join(slug(s.get("Description")) for s in statuses)
        raise ToolError(f"No job status {wanted!r}. Statuses: active, all, {names}.", ErrorCode.INVALID_INPUT)
    return ids


def summary_row(row: dict[str, Any]) -> dict[str, Any]:
    """A `JobSummary/GetJobs` row (camelCase, no refs)."""
    customer = row.get("customer") or {}
    staff = [((m.get("staffMember") or {}).get("fullName")) for m in row.get("jobStaffMembers") or []]
    status = row.get("jobStatus") or {}
    return {
        "job_id": row.get("id"),
        "number": row.get("jobNumber"),
        "customer_id": customer.get("id"),
        "customer": customer.get("customerName"),
        "site_address": row.get("siteAddress"),
        "status": slug(status.get("description")),
        "staff": [name for name in staff if name],
        "description": str(row.get("description") or "").strip(),
        "reference": row.get("customerRef"),
    }


def entity_row(job: dict[str, Any], found: dict[str, dict[str, Any]], statuses: dict[int, str]) -> dict[str, Any]:
    """A Job entity (PascalCase, refs) as a list row."""
    customer = deref(job.get("Customer") or {}, found)
    members = [deref(m, found) for m in job.get("JobStaffMembers") or []]
    staff = [deref(m.get("StaffMember") or {}, found).get("FullName") for m in members]
    return {
        "job_id": job.get("Id"),
        "number": job.get("JobNumber"),
        "customer_id": job.get("CustomerId"),
        "customer": customer.get("CustomerName"),
        "site_address": job.get("SiteAddress"),
        "status": statuses.get(int(job.get("JobStatusId") or 0), ""),
        "staff": [name for name in staff if name],
        "description": str(job.get("Description") or "").strip(),
        "reference": job.get("CustomerRef"),
    }


async def job_detail(api: Api, job_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, dict[str, Any]]]:
    """`Job/GetJobDetailData` with every child block: (job, answer, objects)."""
    blocks = {key: child_block("jobId", job_id) for key in JOB_BLOCKS}
    body = await api.post(
        "Job/GetJobDetailData", {"jobId": job_id, "childDataQueryParams": {"jobId": job_id, **blocks}}
    )
    found = objects(body)
    data = (body or {}).get("Data") or []
    if not data:
        raise ToolError("Tradify has no job with this id (list_jobs).", ErrorCode.INVALID_INPUT)
    return deref(data[0], found), body or {}, found


async def customer_detail(
    api: Api, customer_id: str, page: int = 1, size: int = 50
) -> tuple[dict[str, Any], dict[str, Any], dict[str, dict[str, Any]]]:
    """`Customer/GetCustomerDetailData`, every child block paged alike: (customer, answer, objects)."""
    blocks = {key: child_block("customerId", customer_id, size, page) for key in CUSTOMER_BLOCKS}
    body = await api.post(
        "Customer/GetCustomerDetailData",
        {"customerId": customer_id, "childDataQueryParams": {"customerId": customer_id, **blocks}},
    )
    found = objects(body)
    data = (body or {}).get("Data") or []
    if not data:
        raise ToolError("Tradify has no customer with this id (list_customers).", ErrorCode.INVALID_INPUT)
    return deref(data[0], found), body or {}, found


def child(body: dict[str, Any], found: dict[str, dict[str, Any]], name: str) -> tuple[list[dict[str, Any]], int]:
    """One paged child list of a detail answer: (rows, total)."""
    block = deref(((body.get("ChildData") or {}).get(name)) or {}, found)
    if isinstance(block, list):
        return [deref(r, found) for r in block], len(block)
    return [deref(r, found) for r in block.get("Data") or []], int(block.get("TotalCount") or 0)
