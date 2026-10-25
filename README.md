# Tradify API and MCP server, self-hosted

<!-- mcp-name: dev.cotlet/tradify -->

A **Tradify API** and a **Tradify MCP server** you run on your own computer, in Python, on the session of your own Google Chrome. All 22 Tradify tools we run in production at [Cotlet](https://cotlet.dev/integrations/tradify-api-mcp-server): jobs, job status and notes, customers, quotes with line items, invoices from quotes, quote and invoice email, payments, the Scheduler, reports and timesheets.

Tradify has no public API, no API keys, no webhooks and no official MCP server. Its accounting connectors (Xero, QuickBooks, Sage) sync invoices and bills, not jobs, quotes or the schedule. This repo gives you:

- **MCP server** for Claude Code, Claude Desktop, Cursor, Codex and any MCP client, over stdio or HTTP. [Setup](#mcp-server)
- **REST API** on `http://127.0.0.1:8787/api/v1/tradify`, with OpenAPI docs at `/docs`. [Setup](#rest-api)
- **Python**: `call("list_invoices", {"status": "overdue"})`, plus 9 ready scripts in [`examples/`](https://github.com/cotletdev/tradify-api-mcp-server/blob/main/examples/).

It is for technical people who want to run it themselves, **for noncommercial use only** ([license](#license)). If you want it running 24/7 on a server, kept working when Tradify changes its web app, for a team or a business, use the [hosted version at cotlet.dev](https://cotlet.dev/integrations/tradify-api-mcp-server).

[![Tradify MCP server](https://img.shields.io/badge/Tradify%20MCP-15%20tools-6d4aef)](#all-15-tools)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-141318)](#requirements)
[![License: PolyForm Noncommercial 1.0.0](https://img.shields.io/badge/license-PolyForm%20Noncommercial-141318)](https://github.com/cotletdev/tradify-api-mcp-server/blob/main/LICENSE)
[![MCP Badge](https://lobehub.com/badge/mcp/cotletdev-tradify-api-mcp-server)](https://lobehub.com/mcp/cotletdev-tradify-api-mcp-server)

```bash
uv tool install tradify-api-mcp                  # or: pip install tradify-api-mcp
tradify-mcp connect                                # reads your Tradify session from Chrome
tradify-mcp call list_jobs
claude mcp add tradify -- uvx tradify-api-mcp mcp
```

## Contents

- [How it works](#how-it-works)
- [Requirements](#requirements)
- [Install](#install)
- [Connect your Chrome](#connect-your-chrome)
- [MCP server](#mcp-server)
- [REST API](#rest-api)
- [Python and the example scripts](#python-and-the-example-scripts)
- [All 22 tools](#all-22-tools)
- [Configuration](#configuration)
- [Security and your Tradify account](#security-and-your-tradify-account)
- [Errors](#errors)
- [Self-hosted or hosted](#self-hosted-or-hosted)
- [FAQ](#faq)
- [License](#license)

## How it works

```text
AI agent (MCP) / script (REST, Python) ──▶ tradify-mcp on your computer ──your cookies──▶ go.tradifyhq.com
                                                  ▲
                        tradify-mcp connect ──────┘ reads them once from your Chrome (DevTools Protocol)
```

1. You sign in to Tradify in your own Chrome at [go.tradifyhq.com](https://go.tradifyhq.com/), the way you always do: username, **Continue**, password. Tick **Keep me logged in**.
2. `tradify-mcp connect` attaches to that Chrome through the Chrome DevTools Protocol, reads the tradifyhq.com cookies and saves them to `~/.config/tradify-api-mcp/session.json`, readable by your user only. It never sees or stores your password or a 2-Step code.
3. Every tool call is a request to the `/api` the Tradify web app itself calls, with those cookies, sent with [curl_cffi](https://github.com/lexiforest/curl_cffi), which copies Chrome's TLS fingerprint. Calls that change something carry the app's antiforgery token, read fresh for each tool run. No headless browser runs.

The session lives in one cookie, `SessionId`. With **Keep me logged in** Tradify keeps it for about a month. When Tradify signs you out, the server reads the cookies from Chrome again, if Chrome is open with remote debugging on.

## Requirements

- Python 3.11 or newer.
- Google Chrome 144 or newer, signed in to go.tradifyhq.com. Any Chrome or Chromium works with a [debugging port](#option-b-a-chrome-with-a-debugging-port).
- macOS, Linux or Windows.
- A Tradify account. We build and test with the company owner. An office user sees and does what Tradify lets that user do. `send_quote` and `send_invoice` need 2-Step Security on the login (Settings > Security), because Tradify blocks quote and invoice email without it.

## Install

From [PyPI](https://pypi.org/project/tradify-api-mcp/):

```bash
uv tool install tradify-api-mcp       # or: pipx install tradify-api-mcp, or: pip install tradify-api-mcp
tradify-mcp --version
```

MCP clients can also run it with no install: `uvx tradify-api-mcp mcp`.

From source:

```bash
git clone https://github.com/cotletdev/tradify-api-mcp-server.git
cd tradify-api-mcp-server
python3 -m venv .venv
. .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -e .
tradify-mcp --version
```

With [uv](https://docs.astral.sh/uv/): `uv venv && uv pip install -e .`, then `uv run tradify-mcp ...`.

Setting it up with an AI agent (Claude Code, Codex, Cursor)? Open it in this folder and ask it to set up the repo: [`AGENTS.md`](https://github.com/cotletdev/tradify-api-mcp-server/blob/main/AGENTS.md) tells it every step, and it asks you only for the steps in Chrome.

To update: `uv tool upgrade tradify-api-mcp` (or `pip install -U tradify-api-mcp`), from source `git pull && pip install -e .`. We copy every change of the hosted Tradify tools into this repo.

## Connect your Chrome

### Option A: your everyday Chrome (recommended)

1. Open `chrome://inspect/#remote-debugging` in Chrome and switch **remote debugging** on. Chrome then accepts DevTools connections from programs on this computer, and asks you before each one.
2. Make sure you are signed in at [go.tradifyhq.com](https://go.tradifyhq.com/).
3. Run:

   ```bash
   tradify-mcp connect
   ```

4. Chrome asks whether to allow the connection. Click **Allow**.

```text
Saved 6 Tradify cookies to /Users/you/.config/tradify-api-mcp/session.json
Signed in to Tradify as Dan Novak (Northside Plumbing)
```

You can switch remote debugging off again afterwards. Leave it on if you want the server to pick up a new session by itself after Tradify signs you out.

`connect` looks for Chrome's `DevToolsActivePort` file in the default profile folder. For Chrome Beta, Canary or a custom profile folder, pass `--profile-dir "<folder>"`.

### Option B: a Chrome with a debugging port

Chrome does not open a debugging port on your default profile, so start a separate one, sign in to Tradify there once, and connect to it:

```bash
# macOS
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=9222 --user-data-dir="$HOME/.chrome-tradify"
# Linux
google-chrome --remote-debugging-port=9222 --user-data-dir="$HOME/.chrome-tradify"
# Windows
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%USERPROFILE%\.chrome-tradify"

tradify-mcp connect --cdp http://127.0.0.1:9222
```

A fresh profile is a new device to Tradify, so with 2-Step Security on it asks for a code at sign-in. `--cdp` also takes a `ws://` DevTools URL, for example of a Chrome on another machine reached over an SSH tunnel.

### Option C: paste the cookie by hand

For a server with no Chrome: in Chrome open DevTools on go.tradifyhq.com, **Application > Cookies > https://go.tradifyhq.com**, copy the value of `SessionId`, then:

```bash
tradify-mcp connect --token          # paste it, input is hidden
# or, without a session file:
export TRADIFY_AUTH_TOKEN=...
```

A pasted cookie is not read again from Chrome. Paste a new one when Tradify signs you out.

Check the session at any time:

```bash
tradify-mcp status
```

## MCP server

The MCP server lists every tool with its input schema, a description written for agents, and hints. Read tools are marked read-only, and the tools that reach other people (quote and invoice email, Scheduler bookings) are marked so your client asks before running them.

### Claude Code

```bash
claude mcp add tradify -- uvx tradify-api-mcp mcp
# read only:
claude mcp add tradify -- uvx tradify-api-mcp mcp --read-only
```

### Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "tradify": {
      "command": "uvx",
      "args": ["tradify-api-mcp", "mcp"]
    }
  }
}
```

### Cursor

`~/.cursor/mcp.json`, the same block as Claude Desktop. A ready copy is in [`mcp.json`](https://github.com/cotletdev/tradify-api-mcp-server/blob/main/mcp.json).

### Codex

`~/.codex/config.toml`:

```toml
[mcp_servers.tradify]
command = "uvx"
args = ["tradify-api-mcp", "mcp"]
```

### Over HTTP

`tradify-mcp serve` also serves MCP over streamable HTTP at `http://127.0.0.1:8787/mcp`, for clients that take a URL:

```bash
tradify-mcp serve
claude mcp add --transport http tradify http://127.0.0.1:8787/mcp
```

Then ask your agent things like:

> *New job for Sam Lee at 12 Oak St: replace the hot water cylinder. Book Mike Ross for Thursday morning, about four hours, and email Sam the confirmation.*
>
> *Quote the bathroom rewire at 14 Elm Rd from my notes: 6 hours on the Standard billing rate, 6 LED downlights at $24 each, one extractor fan at $85. Show me the draft before you send it.*
>
> *For every quote accepted this week, create a 30% deposit invoice, skip anything under $500 or already invoiced, and send them after I check the list.*
>
> *Record the bank transfers I paste below against their invoices, then list every invoice still overdue, totalled per customer, oldest first.*

## REST API

```bash
tradify-mcp serve                   # http://127.0.0.1:8787, MCP at /mcp, docs at /docs
```

Each tool has its own route under `/api/v1/tradify`, the same paths as the hosted API at cotlet.dev, so code written against one works with the other. Path parts and the query string are arguments, and a JSON body adds the rest.

```bash
curl 'http://127.0.0.1:8787/api/v1/tradify/jobs?status=to_invoice'
curl 'http://127.0.0.1:8787/api/v1/tradify/invoices?status=overdue'
curl 'http://127.0.0.1:8787/api/v1/tradify/appointments?from=2026-10-27&to=2026-10-31'
curl -X POST http://127.0.0.1:8787/api/v1/tradify/invoices/558f2199-6ca6-489e-bfdf-d4d11cd878e3/payments \
  -H 'Content-Type: application/json' \
  -d '{"amount": 300, "method": "Bank Deposit", "reference": "TRF 20261023"}'
```

Any tool by name, body as its arguments:

```bash
curl -X POST http://127.0.0.1:8787/api/v1/tradify/tools/list_customers -d '{"search": "lee"}'
```

- `GET /api/v1/tradify/tools`: every tool with its route, input schema and an example answer.
- `GET /docs`: interactive OpenAPI docs, `GET /openapi.json` the schema, for n8n, Postman or a generated client.
- Answers are JSON. List tools return `next_cursor`; pass it back as `cursor` for the next page.

The server listens on `127.0.0.1` only. To reach it from another device of yours, set a token, and every request then needs `Authorization: Bearer <token>`:

```bash
TRADIFY_MCP_TOKEN=$(openssl rand -hex 24) tradify-mcp serve --host 0.0.0.0
```

## Python and the example scripts

Straight from Python, no server needed:

```python
from tradify_api_mcp import call
from tradify_api_mcp.scripting import paginate, write_rows

overdue = call("list_invoices", {"status": "overdue"})["invoices"]
week = call("list_appointments", {"from": "2026-10-27", "to": "2026-10-31"})["appointments"]
jobs = list(paginate("list_jobs", {"status": "all"}, "jobs"))
write_rows(jobs, "jobs.csv")
call("update_job_status", job_id="d3bd2e39-af25-4cda-9daf-d9f758f8f0e5", status="complete")
```

Or one tool from the shell: `tradify-mcp call list_quotes status=accepted since=2026-10-01`, or with a JSON object.

Times are wall clock in your company's time zone (Settings > Company). `2026-10-29T08:00` means 8:00 there. A time with an offset is converted to it, and answers carry the company's offset.

Ready scripts in [`examples/`](https://github.com/cotletdev/tradify-api-mcp-server/blob/main/examples/). Each prints a short list or JSON, takes `--out file.csv` or `--out file.json` where it makes sense, and `--help`. The ones that change Tradify only show their plan until you pass `--apply` or `--send`:

| Script | What it does |
|---|---|
| [`overdue_invoices.py`](https://github.com/cotletdev/tradify-api-mcp-server/blob/main/examples/overdue_invoices.py) | Every overdue invoice, totalled per customer, oldest first, with the ones past your last reminder marked. A call list. |
| [`record_payments.py`](https://github.com/cotletdev/tradify-api-mcp-server/blob/main/examples/record_payments.py) | Records the payments of a CSV bank export against invoices by number. Skips an unknown or closed invoice and a payment above the amount due. `--apply`. |
| [`pay_and_close.py`](https://github.com/cotletdev/tradify-api-mcp-server/blob/main/examples/pay_and_close.py) | Records a payment on one invoice and sets its jobs to complete once nothing is due. |
| [`job_from_call.py`](https://github.com/cotletdev/tradify-api-mcp-server/blob/main/examples/job_from_call.py) | Finds or adds the caller, creates the job, and with `--start` books staff after checking their day for overlaps. |
| [`quote_from_notes.py`](https://github.com/cotletdev/tradify-api-mcp-server/blob/main/examples/quote_from_notes.py) | A draft quote from a text file of time and misc lines; `--send` emails it. |
| [`deposit_invoices.py`](https://github.com/cotletdev/tradify-api-mcp-server/blob/main/examples/deposit_invoices.py) | A percentage deposit invoice for every quote accepted lately whose job has no invoice yet. `--apply`, `--send`. |
| [`tomorrows_schedule.py`](https://github.com/cotletdev/tradify-api-mcp-server/blob/main/examples/tomorrows_schedule.py) | Tomorrow's Scheduler grouped by staff member, with job, customer and crew notes. |
| [`export_jobs.py`](https://github.com/cotletdev/tradify-api-mcp-server/blob/main/examples/export_jobs.py) | Jobs to CSV or JSON. `--status`, `--search`. |
| [`export_customers.py`](https://github.com/cotletdev/tradify-api-mcp-server/blob/main/examples/export_customers.py) | Every customer to CSV or JSON, with sites. `--archived`. |

```bash
python examples/overdue_invoices.py
python examples/deposit_invoices.py --percent 30 --minimum 500
python examples/export_jobs.py --status to_invoice --out to_invoice.csv
```

On a schedule, cron on your own computer works while it is on: `0 18 * * * cd ~/tradify-api-mcp-server && .venv/bin/python examples/tomorrows_schedule.py`.

## All 22 tools

IDs come from the list tools: `job_id` from `list_jobs`, `customer_id` from `list_customers`, `quote_id` from `list_quotes`, `invoice_id` from `list_invoices`. Staff are named by full name, as on the Scheduler. `tradify-mcp tools` prints this list, `tradify-mcp tools --json` adds the input schemas.

### Jobs

| Tool | Access | REST route | What it does |
|---|---|---|---|
| `list_jobs` | read | `GET /jobs` | Jobs with number, customer, site address, status and assigned staff. |
| `get_job` | read | `GET /jobs/{job_id}` | Full job: description, site, tasks, notes, appointments, costs, linked quotes and invoices. |
| `create_job` | write | `POST /customers/{customer_id}/jobs` | New job for a customer. It starts as Unassigned. |
| `update_job_status` | write | `PATCH /jobs/{job_id}/status` | Set a status on a job, built-in or one of your custom statuses. |
| `add_job_note` | write | `POST /jobs/{job_id}/notes` | Add a text note to a job's Notes tab. It notifies no one. |

### Customers

| Tool | Access | REST route | What it does |
|---|---|---|---|
| `list_customers` | read | `GET /customers` | Customer profiles with contact details and sites. |
| `get_customer` | read | `GET /customers/{customer_id}` | Customer profile with sites, notes, latest jobs, quotes and invoices, and the balance due. |
| `create_customer` | write | `POST /customers` | New customer profile, optionally with contact details and a physical address. |

### Quotes

| Tool | Access | REST route | What it does |
|---|---|---|---|
| `list_quotes` | read | `GET /quotes` | Quotes with customer, total, quote date, expiry date and status. |
| `get_quote` | read | `GET /quotes/{quote_id}` | Full quote: lines with price and cost, tax, totals, gross profit, dates and invoices made from it. |
| `create_quote` | write | `POST /customers/{customer_id}/quotes` | Draft quote with line items. Nothing is sent until you call send_quote. |
| `send_quote` | write | `POST /quotes/{quote_id}/send` | Approve the quote and email it to the customer with a link to accept or decline online. |

### Invoices and payments

| Tool | Access | REST route | What it does |
|---|---|---|---|
| `list_invoices` | read | `GET /invoices` | Invoices with customer, job, due date, total, amount paid and amount due. |
| `get_invoice` | read | `GET /invoices/{invoice_id}` | Full invoice: lines, tax, totals, every payment with date and method, amount due, jobs and quote. |
| `create_invoice_from_quote` | write | `POST /quotes/{quote_id}/invoices` | Draft invoice from an approved or accepted quote, for all of it or part of it. |
| `send_invoice` | write | `POST /invoices/{invoice_id}/send` | Approve the invoice and email it to the customer, with payment reminders if enabled. |
| `record_payment` | write | `POST /invoices/{invoice_id}/payments` | Record a payment received against an invoice and reduce the amount due. |

### Scheduler

| Tool | Access | REST route | What it does |
|---|---|---|---|
| `list_appointments` | read | `GET /appointments` | Scheduler appointments in a date range, with staff, job, times and notes. |
| `schedule_appointment` | write | `POST /jobs/{job_id}/appointments` | Book a job appointment on the Scheduler for staff, optionally emailing the customer a confirmation. |

### Reports and timesheets

| Tool | Access | REST route | What it does |
|---|---|---|---|
| `get_report` | read | `GET /reports/{report}` | Job profitability, job sheet, staff productivity or timesheet report for a period, as rows. |
| `list_timesheets` | read | `GET /timesheets` | Timesheet entries in a date range: staff, job, customer, billing rate, hours, notes, invoiced. |
| `log_time` | write | `POST /timesheets` | Add a timesheet entry for a staff member, optionally on a job, with billing rate and notes. |

`send_quote` and `send_invoice` email the customer. `schedule_appointment` sends each staff member Tradify's "You've been scheduled" notice, and emails the customer only with `email_customer`. The other write tools stay inside Tradify. Drafts from `create_quote` and `create_invoice_from_quote` reach nobody. `record_payment` refuses more than the amount due and a draft invoice. Part invoices from a quote (`percentage`, `fixed_amount`, `line_items`) need a plan with progress invoicing, which Tradify sells as Pro.

Not in this version: price list items, kits and quote options (quotes take misc and time lines), editing or deleting a quote, invoice or customer, editing or deleting a time entry, moving or cancelling an appointment, report PDFs, job tasks and attachments, bills, purchase orders, enquiries, recurring jobs and forms.

Never built, on purpose: your Tradify sign-in, password and 2-Step Security, and your Tradify plan and billing. Every request passes a guard that refuses any change to the sign-in and account paths of the web app.

## Configuration

| Variable | Default | What it does |
|---|---|---|
| `TRADIFY_MCP_HOME` | `~/.config/tradify-api-mcp` | Folder of `session.json`. |
| `TRADIFY_AUTH_TOKEN` | | The `SessionId` cookie value, used instead of `session.json`. |
| `TRADIFY_PROXY` | | Proxy for every request to Tradify, e.g. `http://user:pass@host:port`. |
| `TRADIFY_MCP_READ_ONLY` | | `1` hides and refuses every tool that changes Tradify (same as `--read-only`). |
| `TRADIFY_MCP_TOKEN` | | Bearer token required by `serve`; needed to listen beyond `127.0.0.1`. |
| `TRADIFY_MCP_HOST`, `TRADIFY_MCP_PORT` | `127.0.0.1`, `8787` | Address of `serve`. |

## Security and your Tradify account

- **Your password never reaches this code.** Only the cookies Chrome already holds are read, and only those of tradifyhq.com.
- **The session file is yours.** `session.json` is created with mode 0600. Anyone who has it can act as you in Tradify, so keep it out of git and shared folders.
- **Local by default.** `serve` binds to `127.0.0.1` and refuses another address without `TRADIFY_MCP_TOKEN`.
- **tradifyhq.com only.** Requests and redirects outside tradifyhq.com are refused.
- **Read-only mode.** `--read-only` or `TRADIFY_MCP_READ_ONLY=1` exposes the 6 read tools only.
- **Some actions reach real people.** A sent quote or invoice lands in your customer's inbox and cannot be deleted in Tradify afterwards, only cancelled. MCP clients ask before running those tools; a script does not, so try it on a customer with your own email address first.

## Errors

The REST API answers `{"error": "<code>", "message": "..."}`. The MCP server returns the same code and message as a tool error.

| Status | Code | What to do |
|---|---|---|
| 401 | `auth_required`, `auth_expired` | No session, or Tradify signed you out. Sign in at go.tradifyhq.com in Chrome and run `tradify-mcp connect`. |
| 403 | `app_permission_denied` | Tradify does not let this login do it. For `send_quote` and `send_invoice`: set up 2-Step Security first. |
| 403 | `scope_denied` | The server runs read-only, or the request would change your Tradify sign-in. |
| 403 | `target_blocked` | Tradify refused the request or showed a bot check. Open the web app in Chrome once, then retry. |
| 409 | `captcha_required` | Tradify asks for a CAPTCHA. Solve it in Chrome. |
| 422 | `invalid_input` | An argument is missing or wrong; the message names it. |
| 429 | `rate_limited` | Tradify is limiting the account. Wait a few minutes. |
| 502 | `target_error` | Tradify answered with an error (its own message is in `message` when it gives one), or changed its web app. `git pull` for the latest tools, or [open an issue](https://github.com/cotletdev/tradify-api-mcp-server/issues). |

## Self-hosted or hosted

| | This repo | [Cotlet, hosted](https://cotlet.dev/integrations/tradify-api-mcp-server) |
|---|---|---|
| Tools | the same 15 | the same 15 |
| Runs | on your computer, while it is on | in the cloud, 24/7 |
| Tradify session | your Chrome, saved in a local file | your own Cloud Browser in the EU, profile encrypted with AES-256-GCM |
| When Tradify changes its web app | `git pull` once we have fixed it | fixed for you, every tool tested daily |
| Approvals | your MCP client asks per call | quote and invoice email and Scheduler bookings wait for your OK, switchable per tool |
| Works with | MCP clients on your machine, local scripts | Claude.ai and ChatGPT connectors, n8n, Make, Zapier, any HTTP client |
| Who may use it | you, for noncommercial use | teams, businesses, agencies |
| Price | free | free 7-day trial with 2,000 credits, no card; then one-time packs from $29 for 5,000 credits |

On the hosted version a successful call uses 10 credits, failed calls are free, and the Cloud Browser uses 50 credits a day while it has an app enabled for agents. [Full pricing](https://cotlet.dev/pricing).

## FAQ

**Does Tradify have an official API?**
No. Tradify publishes no API, developer docs or webhooks (checked 11 Oct 2026). It connects to other tools through built-in integrations: QuickBooks, Xero, Sage, Stripe and Google Calendar. Details: [cotlet.dev/integrations/tradify-api-mcp-server](https://cotlet.dev/integrations/tradify-api-mcp-server).

**Is there a Tradify MCP server for Claude, ChatGPT or Cursor?**
Yes, this one runs on your machine: `tradify-mcp mcp` for Claude Code, Claude Desktop, Cursor and Codex. ChatGPT and Claude.ai connectors need a public HTTPS URL, which the [hosted Tradify MCP server](https://cotlet.dev/integrations/tradify-api-mcp-server) gives you.

**Can it get my Tradify jobs and invoices into another tool?**
Yes. `python examples/export_jobs.py --status all --out jobs.csv` and `python examples/overdue_invoices.py --out overdue.csv` write CSV, and the REST API serves the same lists as JSON to n8n or any HTTP client.

**Why does `send_quote` stop with `app_permission_denied`?**
Tradify blocks quote and invoice email until the login has 2-Step Security. Set it up in Tradify under Settings > Security with a mobile number, then call again. The tool stops before it approves anything, so the quote or invoice stays a draft.

**Which Tradify plan do I need?**
The tools do what your plan lets you do in Tradify. Part invoices from a quote need progress invoicing, which Tradify sells as Pro. On the free Tradify Connect plan only the Scheduler works.

**Does it work outside the US?**
Yes. Tradify runs one web app for every country, and the tools read your company's time zone and tax rates from it.

**Why does it need my Chrome?**
To read your Tradify session without your password and without a 2-Step code. Chrome is used once per sign-in, not for each call.

**What happens when Tradify signs me out?**
Calls fail with `auth_expired`. With Chrome remote debugging on, the server reads the new session on the next call (click Allow when Chrome asks). Otherwise run `tradify-mcp connect` again.

**Can it run on a VPS or in Docker?**
Technically yes, with a pasted cookie or a `session.json` copied from your computer. Tradify then sees your session from a datacenter IP, which looks less like you. For an always-on setup the hosted version keeps your session in your own Cloud Browser on a fixed IP.

**Will my Tradify account get banned?**
Requests carry Chrome's fingerprint and go out one at a time, as you would click. Nobody can promise a platform never acts. Keep to your normal use.

**Can I use it for my trade business or for my clients?**
No. The license allows noncommercial use only, and running your own business counts as business use. For a trade business, a team or client work, use [Cotlet](https://cotlet.dev) or write to [contact@cotlet.dev](mailto:contact@cotlet.dev).

**Can I use the code for anything I like?**
No. The source is public, but the license allows noncommercial use only: no business use.

**A tool broke or I need another one.**
[Open an issue](https://github.com/cotletdev/tradify-api-mcp-server/issues) with the tool name and the error message.

## License

[PolyForm Noncommercial License 1.0.0](https://github.com/cotletdev/tradify-api-mcp-server/blob/main/LICENSE). In short:

- **Allowed:** noncommercial use: you, for your own personal purposes with your own Tradify account, or a charity, school, public research or government body. Changing the code, and sharing it under the same license.
- **Not allowed:** any commercial use, your own business included; client work; selling or offering it, or a service built on it.

---

<p>
  <a href="https://cotlet.dev">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="assets/logo-white.svg">
      <img src="https://raw.githubusercontent.com/cotletdev/tradify-api-mcp-server/main/assets/logo.svg" alt="Cotlet" width="120">
    </picture>
  </a>
</p>

Maintained by [Cotlet](https://cotlet.dev) ([@cotletdev](https://x.com/cotletdev)). Tradify is a trademark of its owner. This project is unofficial and not affiliated with, endorsed or sponsored by Tradify.
