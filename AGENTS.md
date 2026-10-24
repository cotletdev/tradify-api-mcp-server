# AGENTS.md

You are an AI agent in a clone of this repo. It is a self-hosted Tradify API and MCP server: 15 tools that work in the user's own Tradify account (go.tradifyhq.com), through the session of their own Google Chrome. Your usual job is one of three: set it up for the user, use its tools for them, or change its code. Human docs: `README.md`.

## Before you start

- The license allows noncommercial use only (PolyForm Noncommercial 1.0.0, `LICENSE`). Running a trade business (plumbing, electrical, HVAC or any other) is business use. If the user is setting this up for a business, a team or clients, say so and point to the hosted version at https://cotlet.dev/integrations/tradify-api-mcp-server. Do not continue the setup for that use.
- Every tool acts as the user in Tradify. Tools with access `write` create customers, jobs, quotes and invoices, change job status, record payments, book staff on the Scheduler, and email quotes and invoices. `send_quote` and `send_invoice` email the customer, and a sent quote or invoice cannot be deleted in Tradify. `schedule_appointment` notifies each staff member and, with `email_customer`, the customer.

## Set it up for the user

Do the steps yourself. Ask the user only for what needs their hands in Chrome.

1. Check Python: `python3 --version` must be 3.11 or newer.
2. Install in the repo root:

   ```bash
   python3 -m venv .venv && .venv/bin/pip install -e .
   .venv/bin/tradify-mcp --version
   ```

   On Windows the path is `.venv\Scripts\tradify-mcp`. With uv: `uv venv && uv pip install -e .`.
3. Ask the user to do two things in Chrome. You cannot open `chrome://` pages for them.
   - Open `chrome://inspect/#remote-debugging` and switch remote debugging on.
   - Be signed in at https://go.tradifyhq.com/: username, **Continue**, password. Tell them to tick **Keep me logged in**. With 2-Step Security on, Tradify asks a new device for a code.
4. Run `.venv/bin/tradify-mcp connect`. Tell the user to click **Allow** when Chrome asks about the connection. Success prints `Signed in to Tradify as <name> (<company>)`.
5. Check: `.venv/bin/tradify-mcp status`, then `.venv/bin/tradify-mcp call list_jobs`.
6. Add the MCP server to the user's client. Use the absolute path of `.venv/bin/tradify-mcp`:
   - Claude Code: `claude mcp add tradify -- <abs path>/.venv/bin/tradify-mcp mcp`
   - Claude Desktop, Cursor, Codex: the config blocks in `README.md`, section "MCP server".
   - Add `--read-only` after `mcp` if the user only wants to read.
   The client loads new MCP servers on its next start. Tell the user.

If step 4 fails:

| Message | What to do |
|---|---|
| `Chrome remote debugging is off` | Step 3 is not done, or Chrome is Beta, Canary or a custom profile: pass `--profile-dir "<profile folder>"`. |
| `Could not connect to Chrome` | The user did not click Allow, or Chrome is closed. Run `connect` again. |
| `This Chrome is not signed in to Tradify` | The user signs in at go.tradifyhq.com in that Chrome, then run `connect` again. |
| No Chrome on this machine (a server) | The user copies the `SessionId` cookie from Chrome DevTools (Application, Cookies, https://go.tradifyhq.com) and runs `tradify-mcp connect --token` themselves. Never ask them to paste the cookie into the chat. |

## Use the tools

- With the MCP server added, call its tools. Without it: `.venv/bin/tradify-mcp call <tool> key=value ...`, or one JSON object as the argument.
- `.venv/bin/tradify-mcp tools` lists all 15 tools with access and route. `tools --json` adds the input schemas.
- Start with `list_jobs` and `list_customers`. Their `job_id` and `customer_id` are what `get_job`, `create_job`, `create_quote` and `schedule_appointment` take. `list_quotes` gives `quote_id`, `list_invoices` gives `invoice_id`. Staff are named by full name.
- Search `list_customers` before `create_customer`: it matches name, contact, email and phone. Two close matches mean you ask the user which one.
- Times are wall clock in the company's time zone (`2026-10-29T08:00`). Dates are `YYYY-MM-DD`. Read `list_appointments` for the day before `schedule_appointment`: Tradify books over other appointments.
- List tools return `next_cursor`. Pass it back as `cursor` for the next page.
- Before a `write` tool, show the user what you will do and to whom, and get their OK. Show a draft from `create_quote` or `create_invoice_from_quote` before `send_quote` or `send_invoice`.
- For a script or a cron job, use `tradify_api_mcp.scripting` (`call`, `paginate`, `write_rows`) and the scripts in `examples/` as models.
- For a REST API (n8n, other languages): `.venv/bin/tradify-mcp serve`, routes under `http://127.0.0.1:8787/api/v1/tradify`, docs at `/docs`.

Errors come as `<code>: <message>`. `auth_expired` means Tradify signed the session out: the user signs in again in Chrome and you run `connect`. `app_permission_denied` from `send_quote` or `send_invoice` means the login has no 2-Step Security: the user sets it up in Tradify under Settings > Security. `target_error` carries Tradify's own message when it gives one. More codes: `README.md`, section "Errors".

## Keep secrets out

- `~/.config/tradify-api-mcp/session.json` and `TRADIFY_AUTH_TOKEN` give full access to the user's Tradify account. Never print, log, commit or copy their content.
- `serve` listens on 127.0.0.1. Never start it on another address without `TRADIFY_MCP_TOKEN`.

## Change the code

| Path | What | Edit? |
|---|---|---|
| `tradify_api_mcp/tradify/` | the Tradify tools, one file per tool in `tools/` (shared code in `_api.py`, `_jobs.py`, `_quotes.py`, `_invoices.py`, `_send.py`), the app's start-up call and headers in `client.py` | Yes for a local fix, but the next `git pull` brings our version of these files. Report the bug at https://github.com/cotletdev/tradify-api-mcp-server/issues |
| `tradify_api_mcp/app.py` | app name, domains, session cookie, account paths, REST prefix | Rarely |
| `tradify_api_mcp/core/` | `@tool` declaration, errors, the HTTP client with the session (`context.py`), the guard against account changes (`account_guard.py`) | Yes |
| `tradify_api_mcp/session.py` | reading cookies from Chrome over CDP, the session file | Yes |
| `tradify_api_mcp/runner.py`, `api.py`, `mcp_server.py`, `mcp_context.py`, `cli.py` | tool registry, REST API, MCP server, its prompts and resources, command line | Yes |
| `examples/` | scripts for common jobs | Yes |

A new tool is a new file in `tradify_api_mcp/tradify/tools/` with a `@tool(...)` declaration (name, access, input schema, `route`). The registry finds it, and the REST API, the MCP server and the CLI show it without other changes. Every request goes through `_api.Api`: GET for reads, POST with the antiforgery token of the app's start-up answer, and `save` for Breeze `SaveChanges`, which every write uses.

There is no test suite. After a change, run `.venv/bin/tradify-mcp tools` and one read tool against the user's account.
