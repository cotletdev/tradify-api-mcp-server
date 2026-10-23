#!/usr/bin/env python3
"""Record a payment on one Tradify invoice and mark its jobs complete once nothing is due.

    python pay_and_close.py IV00012 --amount 420 --method "Bank Deposit"

Without --amount it records the whole amount due. The jobs are set to complete only when the invoice
is fully paid after the payment.
"""

import argparse

from tradify_api_mcp.scripting import call, paginate, run


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("invoice", help="Invoice number, e.g. IV00012")
    parser.add_argument("--amount", type=float, help="Default: everything still due")
    parser.add_argument("--method", default="Bank Deposit", help="One of your payment methods")
    parser.add_argument("--reference", help="e.g. the bank reference")
    args = parser.parse_args()

    rows = call("list_invoices", {"status": "all", "search": args.invoice, "limit": 10})["invoices"]
    invoice = next((r for r in rows if r["number"].lower() == args.invoice.lower()), None)
    if not invoice:
        raise SystemExit(f"No invoice {args.invoice}.")
    if invoice["status"] not in ("approved", "overdue"):
        raise SystemExit(f"{invoice['number']} is {invoice['status']}, not open for payments.")
    amount = args.amount if args.amount is not None else invoice["due"]
    paid = call(
        "record_payment",
        {"invoice_id": invoice["invoice_id"], "amount": amount, "method": args.method, "reference": args.reference},
    )
    print(f"{invoice['number']} {invoice['customer']}: recorded {amount:.2f}, {paid['due']:.2f} still due")
    if paid["due"] > 0:
        return
    for number in invoice.get("jobs") or []:
        job = next(paginate("list_jobs", {"status": "all", "search": number, "limit": 10}, "jobs"), None)
        if job and job["number"] == number:
            call("update_job_status", {"job_id": job["job_id"], "status": "complete"})
            print(f"{number}: complete")


if __name__ == "__main__":
    run(main)
