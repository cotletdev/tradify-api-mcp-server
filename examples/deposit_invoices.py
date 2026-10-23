#!/usr/bin/env python3
"""A deposit invoice for every Tradify quote accepted in the last days that has no invoice yet.

    python deposit_invoices.py --percent 30 --minimum 500
    python deposit_invoices.py --percent 30 --minimum 500 --apply
    python deposit_invoices.py --percent 30 --apply --send

Without --apply it lists the quotes it would bill. A quote whose job already has an invoice is skipped,
and so is a quote with no job, since nothing shows whether it was billed by hand. --send emails each
draft after it is made.
"""

import argparse
from datetime import date, timedelta

from tradify_api_mcp.scripting import call, paginate, run


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--percent", type=float, default=30.0, help="Deposit as a percent of the quote total")
    parser.add_argument("--minimum", type=float, default=0.0, help="Skip quotes with a smaller total")
    parser.add_argument("--days", type=int, default=7, help="Accepted in the last N days")
    parser.add_argument("--apply", action="store_true", help="Create the draft invoices")
    parser.add_argument("--send", action="store_true", help="With --apply: approve and email each one")
    args = parser.parse_args()

    accepted_since = str(date.today() - timedelta(days=args.days))
    # The since filter is the quote date, so look further back and keep what was accepted lately.
    params = {"status": "accepted", "since": str(date.today() - timedelta(days=90)), "limit": 100}
    quotes = [q for q in paginate("list_quotes", params, "quotes") if (q.get("accepted_on") or "") >= accepted_since]
    for q in quotes:
        head = f"{q['number']} {q['customer']} {q['total']:.2f}"
        if q["total"] < args.minimum:
            print(f"{head}: under {args.minimum:.2f}, skipped")
            continue
        if not q.get("job_id"):
            print(f"{head}: no job, check by hand")
            continue
        if call("get_job", {"job_id": q["job_id"]})["invoices"]:
            print(f"{head}: job {q['job']} already has an invoice, skipped")
            continue
        print(f"{head}: {args.percent:g}% deposit")
        if not args.apply:
            continue
        invoice = call(
            "create_invoice_from_quote", {"quote_id": q["quote_id"], "mode": "percentage", "amount": args.percent}
        )
        print(f"  draft invoice {invoice['total']:.2f}, due {invoice['due_date']}")
        if args.send:
            sent = call("send_invoice", {"invoice_id": invoice["invoice_id"]})
            print(f"  {sent['number']} sent to {', '.join(sent['emailed_to'])}")


if __name__ == "__main__":
    run(main)
