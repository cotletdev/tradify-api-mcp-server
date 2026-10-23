#!/usr/bin/env python3
"""A phone call to a Tradify job: find or add the customer, create the job, book staff if a time is given.

    python job_from_call.py --customer "Sam Lee" --email sam@example.com \
        --description "Replace the hot water cylinder" --site "12 Oak St"
    python job_from_call.py --customer "Sam Lee" --description "Replace the hot water cylinder" \
        --start 2026-10-29T08:00 --hours 4 --staff "Mike Ross" --email-customer

The customer is matched by name, email or phone. Two matches stop the script so you pick one. Before
booking it lists the staff member's appointments that day and refuses a time that overlaps one.
"""

import argparse
from datetime import datetime, timedelta

from tradify_api_mcp.scripting import call, run


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--customer", required=True, help="Name, email or phone to search")
    parser.add_argument("--email", help="For a new customer: email for quotes and confirmations")
    parser.add_argument("--phone", help="For a new customer")
    parser.add_argument("--description", required=True, help="The work, in the caller's words")
    parser.add_argument("--site", help="Site address, if not the customer's")
    parser.add_argument("--reference", help="e.g. a PO number")
    parser.add_argument("--start", help="Appointment start, company time, e.g. 2026-10-29T08:00")
    parser.add_argument("--hours", type=float, default=2.0)
    parser.add_argument("--staff", action="append", help="Staff member full name; repeat for more")
    parser.add_argument("--email-customer", action="store_true", help="Email the customer a confirmation")
    args = parser.parse_args()

    found = call("list_customers", {"search": args.customer, "limit": 10})["customers"]
    if len(found) > 1:
        names = ", ".join(f"{c['name']} ({c.get('email') or c.get('phone') or 'no contact'})" for c in found)
        raise SystemExit(f"More than one customer matches: {names}. Search with an email or phone.")
    if found:
        customer = found[0]
        print(f"Customer: {customer['name']}")
    else:
        customer = call(
            "create_customer",
            {"name": args.customer, "email": args.email, "phone": args.phone, "address": args.site},
        )
        print(f"New customer: {customer['name']}")
    job = call(
        "create_job",
        {
            "customer_id": customer["customer_id"],
            "description": args.description,
            "site_address": args.site,
            "reference": args.reference,
        },
    )
    print(f"Job {job['number']} at {job['site_address']}, {job['status']}")
    if not args.start:
        return
    start = datetime.fromisoformat(args.start)
    end = start + timedelta(hours=args.hours)
    day = start.date().isoformat()
    booked = call("list_appointments", {"from": day, "to": day, "staff": args.staff})["appointments"]
    for a in booked:
        if a["status"] in ("cancelled", "declined"):
            continue
        a_start = datetime.fromisoformat(a["start"]).replace(tzinfo=None)
        a_end = datetime.fromisoformat(a["end"]).replace(tzinfo=None)
        if a_start < end and start < a_end:
            raise SystemExit(f"Overlaps {a['job']} {a['customer']} {a['start'][11:16]}-{a['end'][11:16]}. Not booked.")
    done = call(
        "schedule_appointment",
        {
            "job_id": job["job_id"],
            "start": start.isoformat(),
            "end": end.isoformat(),
            "staff": args.staff,
            "email_customer": args.email_customer,
        },
    )
    staff = ", ".join(done["staff"])
    print(f"Booked {staff} {done['start']} to {done['end'][11:16]}, customer emailed: {done['customer_emailed']}")


if __name__ == "__main__":
    run(main)
