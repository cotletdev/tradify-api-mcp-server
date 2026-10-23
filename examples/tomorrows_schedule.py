#!/usr/bin/env python3
"""Tomorrow's Tradify Scheduler by staff member: where each person goes and when.

    python tomorrows_schedule.py
    python tomorrows_schedule.py --date 2026-10-29 --out day.csv

Cancelled and declined appointments are left out unless you pass --all. Good for an evening cron job:
    0 18 * * * cd ~/tradify-api-mcp-server && .venv/bin/python examples/tomorrows_schedule.py
"""

import argparse
from collections import defaultdict
from datetime import date, timedelta

from tradify_api_mcp.scripting import call, run, write_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--date", default=str(date.today() + timedelta(days=1)), help="YYYY-MM-DD, default tomorrow")
    parser.add_argument("--all", action="store_true", help="Also cancelled and declined appointments")
    parser.add_argument("--out", help="Save the rows to .csv or .json instead of printing them")
    args = parser.parse_args()

    rows = call("list_appointments", {"from": args.date, "to": args.date})["appointments"]
    if not args.all:
        rows = [r for r in rows if r["status"] not in ("cancelled", "declined")]
    rows.sort(key=lambda r: r["start"])
    if args.out:
        write_rows(rows, args.out)
        return
    by_staff: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        for person in r.get("staff") or ["Nobody"]:
            by_staff[person].append(r)
    print(f"{args.date}: {len(rows)} appointments")
    for person, visits in sorted(by_staff.items()):
        print(f"\n{person}")
        for r in visits:
            when = f"{r['start'][11:16]}-{r['end'][11:16]}"
            print(f"  {when}  {r['job']} {r['customer']}  {r.get('notes') or ''}".rstrip())


if __name__ == "__main__":
    run(main)
