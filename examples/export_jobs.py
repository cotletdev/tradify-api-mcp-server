#!/usr/bin/env python3
"""Tradify jobs to CSV or JSON: number, customer, site, status, staff, description, reference.

    python export_jobs.py --out jobs.csv
    python export_jobs.py --status to_invoice --out to_invoice.csv

Without --out it prints JSON. --status takes active (default), all, or one job status such as on_hold.
"""

import argparse

from tradify_api_mcp.scripting import paginate, run, write_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--status", default="active", help="active, all, to_invoice, on_hold, complete ...")
    parser.add_argument("--search", help="Job number, customer or reference")
    parser.add_argument("--out", help="Save to .csv or .json instead of printing JSON")
    args = parser.parse_args()

    params = {"status": args.status, "search": args.search, "limit": 100}
    write_rows(list(paginate("list_jobs", {k: v for k, v in params.items() if v}, "jobs")), args.out)


if __name__ == "__main__":
    run(main)
