"""List customers: the Customers list (Customer/GetCustomerList), active customers, with their sites."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tradify_api_mcp.core.helpers import limit, page_cursor
from tradify_api_mcp.core.tools import tool
from tradify_api_mcp.tradify.tools._api import Api, deref, objects, paged

if TYPE_CHECKING:
    from tradify_api_mcp.core.context import ToolContext

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "search": {"type": "string", "description": "Matches name, contact, email or phone."},
        "archived": {"type": "boolean", "default": False, "description": "List archived customers instead."},
        "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50},
        "cursor": {"type": "string", "description": "next_cursor from the previous call."},
    },
    "required": [],
    "additionalProperties": False,
}

EXAMPLE_RESPONSE: dict[str, Any] = {
    "customers": [
        {
            "customer_id": "7801cbcd-8d5b-4506-afaa-011550798969",
            "name": "Riverside Dental Clinic",
            "contact": "Dana Price",
            "email": "office@example.com",
            "phone": "5550100142",
            "mobile": None,
            "address": "1200 Main St, Kansas City, MO 64105",
            "sites": ["Annex, 1210 Main St, Kansas City, MO 64105"],
        }
    ],
    "next_cursor": None,
}


def address(parts: list[Any]) -> str | None:
    text = ", ".join(str(p).strip().replace("\n", ", ") for p in parts if p and str(p).strip())
    return text or None


def customer_row(customer: dict[str, Any], found: dict[str, dict[str, Any]]) -> dict[str, Any]:
    locations = [deref(loc, found) for loc in customer.get("CustomerLocations") or []]
    return {
        "customer_id": customer.get("Id"),
        "name": customer.get("CustomerName"),
        "contact": customer.get("Contact"),
        "email": customer.get("Email"),
        "phone": customer.get("PhoneNumber"),
        "mobile": customer.get("MobileNumber"),
        "address": address(
            [
                customer.get("PhysicalAddressStreet"),
                customer.get("PhysicalAddressCity"),
                " ".join(
                    str(p)
                    for p in (customer.get("PhysicalAddressRegion"), customer.get("PhysicalAddressPostalCode"))
                    if p
                ),
            ]
        ),
        "sites": [
            text
            for loc in locations
            if not loc.get("IsArchived")
            and (
                text := address(
                    [
                        loc.get("LocationName"),
                        loc.get("AddressStreet"),
                        loc.get("AddressCity"),
                        loc.get("AddressRegion"),
                    ]
                )
            )
        ],
    }


@tool(
    name="list_customers",
    title="List customers",
    access="read",
    description="Customer profiles with contact details and sites.",
    details=(
        "Lists customers by name with contact, email (may be a comma list), phone, mobile, physical address and "
        "sites. search matches name, contact, email or phone, so use it to find the customer_id before creating a "
        "job or quote. archived lists archived customers instead. Pass next_cursor back as cursor."
    ),
    input_schema=INPUT_SCHEMA,
    route="GET /customers",
    example_response=EXAMPLE_RESPONSE,
)
async def list_customers(ctx: ToolContext, args: dict[str, Any]) -> Any:
    api = Api(ctx)
    size = limit(args, 50, 100)
    page = page_cursor(args.get("cursor"))
    body = await api.post(
        "Customer/GetCustomerList",
        paged(
            page,
            size,
            "customerName",
            ascending=True,
            search=str(args.get("search") or ""),
            customerListFilter=1 if args.get("archived") else 0,
        ),
    )
    found = objects(body)
    rows = [deref(r, found) for r in (body or {}).get("Data") or []]
    total = int((body or {}).get("TotalCount") or 0)
    return {
        "customers": [customer_row(r, found) for r in rows],
        "next_cursor": str(page + 1) if page * size < total else None,
    }
