#!/usr/bin/env python3
"""Every overdue Tradify invoice, totalled per customer, oldest due date first: a call list.

    python overdue_invoices.py
    python overdue_invoices.py --reminder-days 7 --out overdue.csv

An invoice more than --reminder-days past its due date is marked: Tradify's automatic reminders have
stopped for it, so nobody else will chase it. Part-paid invoices show only what is still due.
"""

import argparse
from collections import defaultdict
from datetime import date

from tradify_api_mcp.scripting import paginate, run, write_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--reminder-days", type=int, default=7, help="Days after the due date your last reminder goes")
    parser.add_argument("--out", help="Save the invoices to .csv or .json instead of printing the list")
    args = parser.parse_args()

    rows = list(paginate("list_invoices", {"status": "overdue", "limit": 100}, "invoices"))
    if args.out:
        write_rows(rows, args.out)
        return
    by_customer: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_customer[r["customer"]].append(r)
    today = date.today()
    order = sorted(by_customer.items(), key=lambda item: min(r["due_date"] or "9999" for r in item[1]))
    print(f"{len(rows)} overdue invoices, {sum(r['due'] for r in rows):.2f} still due")
    for customer, invoices in order:
        print(f"\n{customer}: {sum(r['due'] for r in invoices):.2f}")
        for r in sorted(invoices, key=lambda r: r["due_date"] or ""):
            late = (today - date.fromisoformat(r["due_date"])).days if r["due_date"] else 0
            flag = "  past the last reminder" if late > args.reminder_days else ""
            print(f"  {r['number']}  due {r['due_date']} ({late} days late)  {r['due']:.2f} of {r['total']:.2f}{flag}")


if __name__ == "__main__":
    run(main)
