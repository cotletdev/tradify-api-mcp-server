#!/usr/bin/env python3
"""A draft Tradify quote from your site notes in a small text file, sent only with --send.

    python quote_from_notes.py --customer "Sam Lee" notes.txt
    python quote_from_notes.py --customer "Sam Lee" notes.txt --send

One line per item in notes.txt:

    time 6 Standard                 6 hours on the Standard billing rate
    misc 6 24 LED downlight         6 units at 24.00
    misc 1 85 Extractor fan

Prices are before tax. Tax and the expiry date follow your Tradify settings.
"""

import argparse

from tradify_api_mcp.scripting import call, run


def parse(line: str) -> dict:
    kind, rest = line.split(maxsplit=1)
    if kind == "time":
        hours, *rate = rest.split(maxsplit=1)
        item = {"type": "time", "quantity": float(hours)}
        if rate:
            item["billing_rate"] = rate[0].strip()
        return item
    quantity, price, description = rest.split(maxsplit=2)
    return {"type": "misc", "quantity": float(quantity), "unit_price": float(price), "description": description.strip()}


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("notes", help="Text file, one line item per line")
    parser.add_argument("--customer", required=True, help="Name, email or phone to search")
    parser.add_argument("--description", help="Shown on the quote")
    parser.add_argument("--send", action="store_true", help="Approve the quote and email it to the customer")
    args = parser.parse_args()

    with open(args.notes, encoding="utf-8") as fh:
        lines = [parse(line) for line in fh if line.strip() and not line.startswith("#")]
    found = call("list_customers", {"search": args.customer, "limit": 10})["customers"]
    if len(found) != 1:
        raise SystemExit(f"{len(found)} customers match {args.customer!r}; search with an email or phone.")
    quote = call(
        "create_quote",
        {"customer_id": found[0]["customer_id"], "line_items": lines, "description": args.description},
    )
    print(f"{quote['number']} for {quote['customer']}, {quote['status']}, expires {quote['expiry_date']}")
    for line in quote["lines"]:
        price = f"{line['quantity']:>6} x {line['unit_price']:>8.2f} = {line['amount']:>9.2f}"
        print(f"  {line['description']:<30} {price}")
    print(f"  subtotal {quote['subtotal']:.2f}  tax {quote['tax']:.2f}  total {quote['total']:.2f}")
    if args.send:
        sent = call("send_quote", {"quote_id": quote["quote_id"]})
        print(f"Sent to {', '.join(sent['emailed_to'])}")


if __name__ == "__main__":
    run(main)
