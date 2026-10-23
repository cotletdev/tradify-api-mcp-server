"""Invoices: status words, list rows, the invoice detail call."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tradify_api_mcp.core.errors import ErrorCode, ToolError
from tradify_api_mcp.tradify.tools._api import INVOICE_CANCELLED, INVOICE_DRAFT, Api, deref, iso_date, money, objects
from tradify_api_mcp.tradify.tools._api import parse_local as parse

if TYPE_CHECKING:
    from datetime import date

# The Invoices list filters (InvoiceListFilter of the bundle).
LIST_FILTERS = {"draft": 0, "approved": 1, "paid": 2, "overdue": 3, "cancelled": 5, "all": 6}


def _field(row: dict[str, Any], name: str) -> Any:
    """A field of a PascalCase entity or a camelCase list row."""
    return row.get(name, row.get(name[:1].lower() + name[1:]))


def invoice_status(row: dict[str, Any], today: date) -> str:
    """draft, cancelled, paid, overdue (approved, past due date, money due) or approved."""
    status = int(_field(row, "Status") or 0)
    if status == INVOICE_DRAFT:
        return "draft"
    if status == INVOICE_CANCELLED:
        return "cancelled"
    if _field(row, "IsFullyPaid"):
        return "paid"
    due_date = parse(_field(row, "DueDate"))
    if due_date and due_date.date() < today and money(_field(row, "Due")) > 0:
        return "overdue"
    return "approved"


def summary_row(row: dict[str, Any], today: date) -> dict[str, Any]:
    """An `InvoiceSummary/GetInvoices` row (camelCase, no refs)."""
    jobs = [((j.get("job") or {}).get("jobNumber")) for j in row.get("invoiceJobs") or []]
    customer = row.get("customer") or {}
    return {
        "invoice_id": row.get("id"),
        "number": row.get("invoiceNumber"),
        "customer_id": customer.get("id"),
        "customer": customer.get("customerName"),
        "jobs": [job for job in jobs if job],
        "invoice_date": iso_date(row.get("invoiceDate")),
        "due_date": iso_date(row.get("dueDate")),
        "total": money(row.get("total")),
        "paid": money(row.get("paid")),
        "due": money(row.get("due")),
        "status": invoice_status(row, today),
    }


def entity_row(invoice: dict[str, Any], found: dict[str, dict[str, Any]], today: date) -> dict[str, Any]:
    """An Invoice entity (PascalCase, refs) as a list row."""
    links = [deref(j, found) for j in invoice.get("InvoiceJobs") or []]
    jobs = [deref(link.get("Job") or {}, found).get("JobNumber") for link in links]
    customer = deref(invoice.get("Customer") or {}, found)
    return {
        "invoice_id": invoice.get("Id"),
        "number": invoice.get("InvoiceNumber"),
        "customer_id": invoice.get("CustomerId"),
        "customer": customer.get("CustomerName"),
        "jobs": [job for job in jobs if job],
        "invoice_date": iso_date(invoice.get("InvoiceDate")),
        "due_date": iso_date(invoice.get("DueDate")),
        "total": money(invoice.get("Total")),
        "paid": money(invoice.get("Paid")),
        "due": money(invoice.get("Due")),
        "status": invoice_status(invoice, today),
    }


async def invoice_detail(api: Api, invoice_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, dict[str, Any]]]:
    """`Invoice/GetInvoiceDetailData`: (invoice, answer, objects). LookupData has the payment methods."""
    body = await api.get("Invoice/GetInvoiceDetailData", {"invoiceId": invoice_id})
    found = objects(body)
    data = (body or {}).get("Data") or []
    if not data:
        raise ToolError("Tradify has no invoice with this id (list_invoices).", ErrorCode.INVALID_INPUT)
    return deref(data[0], found), body or {}, found
