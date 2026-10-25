"""Get report: one of the Reports page's four reports as rows, from the CSV the panel downloads (Report/*CSV).

The panel posts the report's filters and gets back a `DownloadableAttachment` whose `Data` is the CSV in
base64, the same file "Download CSV file" saves. Recorded 25.10.2026 (`../MAP.md`, Reports).
"""

from __future__ import annotations

import base64
import binascii
import csv
import io
import re
from datetime import date
from typing import TYPE_CHECKING, Any

from tradify_api_mcp.core.errors import ErrorCode, ToolError
from tradify_api_mcp.core.tools import tool
from tradify_api_mcp.tradify.tools._api import Api, app_date, deref, objects

if TYPE_CHECKING:
    from tradify_api_mcp.core.context import ToolContext

# report: (CSV action, lookup action with the staff list, kind of filters)
REPORTS = {
    "job_profitability": ("GenerateAndDownloadJobFinancialReportCSV", "GetJobFinancialReportLookupData", "job"),
    "job_sheet": ("GenerateAndDownloadJobSheetReportCSV", "GetJobsheetReportLookupData", "job"),
    "staff_productivity": ("GenerateAndDownloadProductivityReportCSV", "GetProductivityReportLookupData", "staff"),
    "timesheets": ("GenerateAndDownloadTimesheetReportCSV", "GetTimesheetReportLookupData", "time"),
}
DATE_BASIS = {"entered": 1, "scheduled": 2}
MAX_DAYS = 366
MAX_ROWS = 1000
# Money and costs carry decimals ("1,020.00"); whole numbers stay text, since phone numbers are whole too.
_NUMBER = re.compile(r"^-?(\d{1,3}(,\d{3})+|\d+)\.\d+$")

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "report": {
            "type": "string",
            "enum": list(REPORTS),
            "description": (
                "job_profitability (estimated and actual cost, invoiced, to invoice, gross profit and margin per job, "
                "split into time and materials), job_sheet (jobs with site, staff, schedule, contacts, labour and "
                "cost), staff_productivity (billable and non-billable hours per staff member) or timesheets (time "
                "logged per job and staff member)."
            ),
        },
        "from": {"type": "string", "format": "date", "description": "First day of the period."},
        "to": {"type": "string", "format": "date", "description": "Last day of the period, up to a year after from."},
        "date_basis": {
            "type": "string",
            "enum": list(DATE_BASIS),
            "default": "entered",
            "description": "job_profitability and job_sheet: jobs entered in the period (default) or scheduled in it.",
        },
        "customer_id": {
            "type": "string",
            "description": "job_profitability, job_sheet, timesheets: only this customer (list_customers).",
        },
        "staff": {"type": "string", "description": "Only this staff member, by full name."},
        "include_inactive_jobs": {
            "type": "boolean",
            "default": False,
            "description": "job_sheet: also complete and cancelled jobs.",
        },
    },
    "required": ["report", "from", "to"],
    "additionalProperties": False,
}

EXAMPLE_RESPONSE: dict[str, Any] = {
    "report": "job_profitability",
    "from": "2026-10-01",
    "to": "2026-10-31",
    "columns": [
        "job_no",
        "customer",
        "break_down",
        "estimated_cost",
        "actual_cost",
        "invoiced",
        "to_invoice",
        "gross_profit",
        "profit_margin",
    ],
    "rows": [
        {
            "job_no": "JB00002",
            "customer": "Maple Street Bakery",
            "break_down": "Materials",
            "estimated_cost": 410.0,
            "actual_cost": 0.0,
            "invoiced": 1020.0,
            "to_invoice": 0.0,
            "gross_profit": 1020.0,
            "profit_margin": "100%",
        },
        {
            "job_no": "JB00002",
            "customer": "Maple Street Bakery",
            "break_down": "Total",
            "estimated_cost": 410.0,
            "actual_cost": 0.0,
            "invoiced": 1020.0,
            "to_invoice": 0.0,
            "gross_profit": 1020.0,
            "profit_margin": "100%",
        },
    ],
    "truncated": False,
}


def column(name: str) -> str:
    """A CSV header as a key: "Job No" -> job_no, "Category #1" -> category_1, "%" -> percent."""
    key = re.sub(r"[^a-z0-9]+", "_", name.lower().replace("%", " percent ")).strip("_")
    return key or "column"


def cell(value: str) -> Any:
    """A CSV value: decimals as numbers ("1,020.00" -> 1020.0), blanks as null, the rest as text."""
    text = value.strip()
    if not text:
        return None
    if _NUMBER.match(text):
        return float(text.replace(",", ""))
    return text


def parse_csv(text: str) -> tuple[list[str], list[dict[str, Any]]]:
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    header = next(reader, [])
    columns: list[str] = []
    for name in header:
        key = column(name)
        while key in columns:
            key = f"{key}_2"
        columns.append(key)
    rows = [dict(zip(columns, (cell(v) for v in values), strict=False)) for values in reader if any(values)]
    return columns, rows


def _day(value: Any, name: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ToolError(f"{name} must be a date like 2026-10-31.", ErrorCode.INVALID_INPUT) from exc


async def _staff_id(api: Api, lookup: str, name: str) -> str:
    body = await api.get(f"Report/{lookup}")
    found = objects(body)
    people = [deref(s, found) for s in (body or {}).get("StaffMembers") or []]
    match = next((p for p in people if str(p.get("FullName") or "").lower() == name.lower()), None)
    if match is None:
        known = ", ".join(str(p.get("FullName")) for p in people if p.get("FullName"))
        raise ToolError(f"No staff member {name!r}. Staff: {known}.", ErrorCode.INVALID_INPUT)
    return str(match["Id"])


@tool(
    name="get_report",
    title="Get report",
    access="read",
    description="Job profitability, job sheet, staff productivity or timesheet report for a period, as rows.",
    details=(
        "Runs one report of Tradify's Reports page for the days from to to (both included, at most a year) and "
        "returns the rows of its CSV download, amounts as numbers. job_profitability gives three rows per job "
        "(Time, Materials, Total) with estimated cost from quotes, actual cost, invoiced, to invoice, gross profit "
        "and margin. job_sheet lists the jobs with site, staff, schedule, contacts, entered by and on. "
        "staff_productivity gives billable, non-billable and total hours (h:mm) per staff member. timesheets lists "
        "each time entry with job, customer, staff member, billing rate, notes, date and hours. date_basis picks "
        "jobs by entry or by schedule date. Stops at 1000 rows with truncated true."
    ),
    input_schema=INPUT_SCHEMA,
    route="GET /reports/{report}",
    example_response=EXAMPLE_RESPONSE,
    timeout_s=120,
)
async def get_report(ctx: ToolContext, args: dict[str, Any]) -> Any:
    api = Api(ctx)
    report = str(args["report"])
    action, lookup, kind = REPORTS[report]
    first, last = _day(args["from"], "from"), _day(args["to"], "to")
    if last < first or (last - first).days > MAX_DAYS:
        raise ToolError("to must be on or after from, at most a year later.", ErrorCode.INVALID_INPUT)
    staff_id = await _staff_id(api, lookup, str(args["staff"]).strip()) if args.get("staff") else None
    body: dict[str, Any] = {"dateFrom": app_date(first), "dateTo": app_date(last), "staffMemberId": staff_id}
    customer_id = args.get("customer_id") or None
    if kind == "job":
        body |= {
            "dateType": DATE_BASIS[str(args.get("date_basis") or "entered")],
            "customerId": customer_id,
            "jobTypeId": None,
            "jobType2Id": None,
        }
        body |= {"showChart": False} if report == "job_profitability" else {}
        body |= {"showInactiveJobs": bool(args.get("include_inactive_jobs"))} if report == "job_sheet" else {}
    elif kind == "time":
        body |= {"showDetail": True, "customerId": customer_id or ""}
    answer = await api.post(f"Report/{action}", body)
    data = (answer or {}).get("Data") if isinstance(answer, dict) else None
    try:
        text = base64.b64decode(str(data or "")).decode("utf-8-sig", "replace")
    except (binascii.Error, ValueError):
        raise ToolError("Tradify sent a report this tool cannot read.", ErrorCode.TARGET_ERROR) from None
    columns, rows = parse_csv(text)
    return {
        "report": report,
        "from": first.isoformat(),
        "to": last.isoformat(),
        "columns": columns,
        "rows": rows[:MAX_ROWS],
        "truncated": len(rows) > MAX_ROWS,
    }
