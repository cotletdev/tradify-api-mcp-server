#!/usr/bin/env python3
"""Record the payments in a CSV file (bank export) against their Tradify invoices.

    python record_payments.py payments.csv
    python record_payments.py payments.csv --apply

The CSV needs the columns invoice (number, e.g. IV00012), amount, and optionally date (YYYY-MM-DD),
method (e.g. Bank Deposit) and reference. Without --apply it only matches the rows and shows what it
would record. A payment above the amount due, an invoice that is not found once, and a draft, paid
or cancelled invoice are skipped.
"""

import argparse
import csv

from tradify_api_mcp.core.errors import ToolError
from tradify_api_mcp.scripting import call, run


def find_invoice(number: str) -> dict | None:
    rows = call("list_invoices", {"status": "all", "search": number, "limit": 10})["invoices"]
    exact = [r for r in rows if r["number"].lower() == number.lower()]
    return exact[0] if len(exact) == 1 else None


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("csv", help="CSV with invoice, amount, date, method, reference")
    parser.add_argument("--apply", action="store_true", help="Record the payments")
    args = parser.parse_args()

    with open(args.csv, newline="", encoding="utf-8") as fh:
        payments = list(csv.DictReader(fh))
    for p in payments:
        number, amount = p["invoice"].strip(), float(p["amount"])
        invoice = find_invoice(number)
        if not invoice:
            print(f"{number}: not found, skipped")
            continue
        if invoice["status"] not in ("approved", "overdue"):
            print(f"{number}: {invoice['status']}, not open for payments, skipped")
            continue
        if amount > invoice["due"] + 0.005:
            print(f"{number}: {amount:.2f} is more than the {invoice['due']:.2f} due, skipped")
            continue
        kind = "full" if abs(amount - invoice["due"]) < 0.005 else "part"
        print(f"{number} {invoice['customer']}: {amount:.2f} of {invoice['due']:.2f} due ({kind} payment)")
        if not args.apply:
            continue
        params = {"invoice_id": invoice["invoice_id"], "amount": amount}
        params.update({k: p[k] for k in ("date", "method", "reference") if p.get(k)})
        try:
            done = call("record_payment", params)
            print(f"  recorded, {done['due']:.2f} still due, status {done['status']}")
        except ToolError as err:
            print(f"  not recorded: {err}")


if __name__ == "__main__":
    run(main)
