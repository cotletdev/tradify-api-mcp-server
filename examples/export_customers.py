#!/usr/bin/env python3
"""Every Tradify customer to CSV or JSON: name, contact, email, phone, mobile, address, sites.

    python export_customers.py --out customers.csv
    python export_customers.py --archived --out archived.json

Without --out it prints JSON.
"""

import argparse

from tradify_api_mcp.scripting import paginate, run, write_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--search", help="Only customers whose name, contact, email or phone matches")
    parser.add_argument("--archived", action="store_true", help="Archived customers instead")
    parser.add_argument("--out", help="Save to .csv or .json instead of printing JSON")
    args = parser.parse_args()

    params = {"search": args.search, "archived": args.archived or None, "limit": 100}
    write_rows(list(paginate("list_customers", {k: v for k, v in params.items() if v}, "customers")), args.out)


if __name__ == "__main__":
    run(main)
