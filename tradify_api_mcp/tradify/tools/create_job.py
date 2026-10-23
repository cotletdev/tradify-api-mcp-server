"""Create job: a new Job entity for a customer through Breeze SaveChanges, status Unassigned."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tradify_api_mcp.core.tools import tool
from tradify_api_mcp.tradify.tools._api import EMPTY_ID, Api, entity, html_text, new_id
from tradify_api_mcp.tradify.tools._jobs import customer_detail
from tradify_api_mcp.tradify.tools.list_customers import address

if TYPE_CHECKING:
    from tradify_api_mcp.core.context import ToolContext

UNASSIGNED = 1

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "customer_id": {"type": "string", "minLength": 1, "description": "From list_customers or create_customer."},
        "description": {"type": "string", "minLength": 1, "maxLength": 4000, "description": "What the work is."},
        "site_address": {"type": "string", "maxLength": 500, "description": "Default: the customer's address."},
        "reference": {"type": "string", "maxLength": 255, "description": "Your reference, e.g. a PO number."},
        "contact": {"type": "string", "maxLength": 255, "description": "Job contact. Default: the customer's."},
        "contact_phone": {"type": "string", "maxLength": 50, "description": "Default: the customer's phone."},
    },
    "required": ["customer_id", "description"],
    "additionalProperties": False,
}

EXAMPLE_RESPONSE: dict[str, Any] = {
    "job_id": "5b0f1d0e-8e1a-4a6c-9a8e-2f4b7c9d1e30",
    "number": "JB00002",
    "customer_id": "15c3fe99-d636-48f1-b8fd-b245ada95751",
    "customer": "Oakline Property Management",
    "site_address": "77 Elm Ave, Kansas City, MO 64111",
    "description": "Service boiler in unit 4B",
    "reference": "PO-5521",
    "status": "unassigned",
}


@tool(
    name="create_job",
    title="Create job",
    access="write",
    description="New job for a customer. It starts as Unassigned.",
    details=(
        "Creates a job for a customer, as New Job does, and Tradify gives it the next job number. It starts "
        "Unassigned; schedule_appointment books staff on it. Contact, phone and site address default to the "
        "customer's. It reaches no one and stays inside Tradify."
    ),
    input_schema=INPUT_SCHEMA,
    route="POST /customers/{customer_id}/jobs",
    example_response=EXAMPLE_RESPONSE,
)
async def create_job(ctx: ToolContext, args: dict[str, Any]) -> Any:
    api = Api(ctx)
    customer, _, _ = await customer_detail(api, str(args["customer_id"]), size=1)
    options = await api.options()
    text = str(args["description"]).strip()
    site = args.get("site_address") or address(
        [
            customer.get("PhysicalAddressStreet"),
            customer.get("PhysicalAddressCity"),
            customer.get("PhysicalAddressRegion"),
        ]
    )
    fields: dict[str, Any] = {
        "Id": new_id(),
        "JobNumber": "New",
        "JobSequence": 0,
        "CustomerId": customer.get("Id"),
        "JobStatusId": UNASSIGNED,
        "PriceGroupId": customer.get("PriceGroupId") or options.get("DefaultPriceGroupId"),
        "TaxCalculationMethodId": customer.get("TaxCalculationMethodId")
        or options.get("DefaultTaxCalculationMethodId"),
        "CustomerRef": args.get("reference"),
        "Description": text,
        "FormattedDescription": html_text(text),
        "JobContact": args.get("contact") or customer.get("Contact") or customer.get("CustomerName"),
        "JobContactPhoneNumber": args.get("contact_phone")
        or customer.get("PhoneNumber")
        or customer.get("MobileNumber"),
        "SiteAddress": site,
        "HasSignature": False,
        "TenantId": EMPTY_ID,
        "__unmapped": {"SourceName": None, "SourceId": None, "SourceTypeName": None},
        **await api.created(),
    }
    saved = await api.save([entity("Job", "Jobs", fields)])
    job = next((e for e in saved if e.get("Id") == fields["Id"]), {})
    return {
        "job_id": fields["Id"],
        "number": job.get("JobNumber"),
        "customer_id": customer.get("Id"),
        "customer": customer.get("CustomerName"),
        "site_address": job.get("SiteAddress", site),
        "description": text,
        "reference": args.get("reference"),
        "status": "unassigned",
    }
