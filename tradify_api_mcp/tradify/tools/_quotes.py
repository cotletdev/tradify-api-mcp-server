"""Quotes and the money maths quotes and invoices share.

The panel computes every line amount, tax row and total itself and the server stores what it gets, so the
tools do the same sums as the bundle (EstimateLine.calcTotals, Estimate.calcTotals, TaxHelper.calculateTax).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tradify_api_mcp.core.errors import ErrorCode, ToolError
from tradify_api_mcp.tradify.tools._api import (
    QUOTE_STATUSES,
    TAX_INCLUSIVE,
    Api,
    deref,
    objects,
    parse_local,
    round_money,
    tax_of,
)

if TYPE_CHECKING:
    from datetime import date

QUOTE_APPROVED = 2


def quote_status(status: int, expiry: Any, today: date) -> str:
    """The quote's status word; awaiting acceptance past the expiry date is expired."""
    word = QUOTE_STATUSES.get(status, "")
    expires = parse_local(expiry)
    if status == QUOTE_APPROVED and expires and expires.date() < today:
        return "expired"
    return word


def line_amounts(quantity: float, unit_price: float, unit_cost: float, rate: float, method: int) -> dict[str, float]:
    """Amount, Tax, CostAmount and GrossProfit of one line, no discount."""
    amount = round_money(unit_price * quantity)
    tax = tax_of(amount, rate, method)
    cost = round_money(unit_cost * quantity)
    net = amount - tax if method == TAX_INCLUSIVE else amount
    return {
        "Amount": amount,
        "Tax": tax,
        "CostAmount": cost,
        "GrossProfit": round_money(net - cost),
        "DiscountAmount": 0.0,
        "UnitDiscount": 0.0,
        "DiscountPercentage": 0.0,
    }


def tax_rows(lines: list[dict[str, Any]], method: int, on_lines: bool) -> list[dict[str, Any]]:
    """One tax total per rate: Description, Rate, Amount (lines' sum) and Total (the tax)."""
    groups: dict[tuple[str, float], list[dict[str, Any]]] = {}
    for line in lines:
        key = (str(line.get("TaxRateDescription") or ""), float(line.get("TaxRatePercentage") or 0))
        groups.setdefault(key, []).append(line)
    rows = []
    for (description, rate), members in groups.items():
        amount = round_money(sum(float(m["Amount"]) for m in members))
        total = round_money(sum(float(m["Tax"]) for m in members)) if on_lines else tax_of(amount, rate, method)
        rows.append({"Description": description, "Rate": rate, "Amount": amount, "Total": total})
    return rows


def totals(lines: list[dict[str, Any]], taxes: list[dict[str, Any]], method: int) -> dict[str, float]:
    """SubTotal, Tax, Total, Cost and GrossProfit of a document."""
    subtotal = round_money(sum(float(line["Amount"]) for line in lines))
    tax = round_money(sum(float(t["Total"]) for t in taxes))
    cost = round_money(sum(float(line.get("CostAmount") or 0) for line in lines))
    total = subtotal if method == TAX_INCLUSIVE else round_money(subtotal + tax)
    net = subtotal - tax if method == TAX_INCLUSIVE else subtotal
    return {
        "SubTotal": subtotal,
        "Tax": tax,
        "Total": total,
        "Cost": cost,
        "GrossProfit": round_money(net - cost),
        "Discount": 0.0,
    }


async def quote_detail(api: Api, quote_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, dict[str, Any]]]:
    """`Estimate/GetEstimateDetailData`: (quote, answer, objects)."""
    body = await api.get("Estimate/GetEstimateDetailData", {"estimateId": quote_id})
    found = objects(body)
    data = (body or {}).get("Data") or []
    if not data:
        raise ToolError("Tradify has no quote with this id (list_quotes).", ErrorCode.INVALID_INPUT)
    return deref(data[0], found), body or {}, found


def quote_lines(quote: dict[str, Any], found: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    lines = sorted(
        (deref(line, found) for line in quote.get("EstimateLines") or []), key=lambda x: x.get("SortOrder") or 0
    )
    return [
        {
            "description": line.get("Description"),
            "quantity": line.get("Quantity"),
            "unit_price": line.get("UnitPrice"),
            "amount": line.get("Amount"),
        }
        for line in lines
    ]
