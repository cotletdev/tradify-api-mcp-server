"""Create customer: a new Customer entity through Breeze SaveChanges, with the company's default price group."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tradify_api_mcp.core.tools import tool
from tradify_api_mcp.tradify.tools._api import EMPTY_ID, Api, entity, new_id

if TYPE_CHECKING:
    from tradify_api_mcp.core.context import ToolContext

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "minLength": 1, "maxLength": 255, "description": "Customer or company name."},
        "contact": {"type": "string", "maxLength": 255, "description": "Contact person. Default: the name."},
        "email": {"type": "string", "maxLength": 500, "description": "Email for quotes and invoices; commas for more."},
        "phone": {"type": "string", "maxLength": 50},
        "mobile": {"type": "string", "maxLength": 50},
        "address": {"type": "string", "maxLength": 500, "description": "Street address."},
        "city": {"type": "string", "maxLength": 100},
        "state": {"type": "string", "maxLength": 100, "description": "State or region."},
        "postal_code": {"type": "string", "maxLength": 20},
    },
    "required": ["name"],
    "additionalProperties": False,
}

EXAMPLE_RESPONSE: dict[str, Any] = {
    "customer_id": "0c1f5a3e-2b7d-4c55-9f0e-7d3b8f1c2a64",
    "name": "Maple Street Bakery",
    "email": "orders@example.com",
    "status": "created",
}


@tool(
    name="create_customer",
    title="Create customer",
    access="write",
    description="New customer profile, optionally with contact details and a physical address.",
    details=(
        "Creates an active customer with the company's default price group, document theme and tax settings, as "
        "the New Customer form does. email may hold several addresses separated by commas; quotes and invoices go "
        "there. It reaches no one and stays inside Tradify."
    ),
    input_schema=INPUT_SCHEMA,
    route="POST /customers",
    example_response=EXAMPLE_RESPONSE,
)
async def create_customer(ctx: ToolContext, args: dict[str, Any]) -> Any:
    api = Api(ctx)
    options = await api.options()
    name = str(args["name"]).strip()
    fields: dict[str, Any] = {
        "Id": new_id(),
        "CustomerName": name,
        "Contact": str(args.get("contact") or name).strip(),
        "Email": args.get("email"),
        "PhoneNumber": args.get("phone"),
        "MobileNumber": args.get("mobile"),
        "PhysicalAddressStreet": args.get("address"),
        "PhysicalAddressCity": args.get("city"),
        "PhysicalAddressRegion": args.get("state"),
        "PhysicalAddressPostalCode": args.get("postal_code"),
        "IsTaxExempt": False,
        "IsArchived": False,
        "TaxCalculationMethodId": options.get("DefaultTaxCalculationMethodId") or 1,
        "PriceGroupId": options.get("DefaultPriceGroupId"),
        "DocumentFormatId": options.get("DefaultDocumentFormatId"),
        "InvoiceEmailMode": 3,
        "EstimateEmailMode": 3,
        "JobServiceReportEmailMode": 3,
        "FormEmailMode": 3,
        "TenantId": EMPTY_ID,
        **await api.created(),
    }
    saved = await api.save([entity("Customer", "Customers", fields)])
    customer = next((e for e in saved if e.get("Id") == fields["Id"]), saved[0] if saved else fields)
    return {
        "customer_id": customer.get("Id"),
        "name": customer.get("CustomerName"),
        "email": customer.get("Email"),
        "status": "created",
    }
