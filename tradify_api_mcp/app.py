"""Everything the server knows about Tradify outside `tradify/`: names, domains and the session cookie.

The rest of the package reads these values and never names the app itself.
"""

from __future__ import annotations

NAME = "Tradify"
SLUG = "tradify"
# The command and the prefix of every environment variable (TRADIFY_AUTH_TOKEN, TRADIFY_MCP_TOKEN ...).
CLI = "tradify-mcp"
ENV = "TRADIFY"
# Requests may reach only these hosts and their subdomains. Their cookies are read from Chrome.
# The web app at go.tradifyhq.com calls its own /api/* on the same host.
DOMAINS = ("tradifyhq.com",)
# Present only while signed in. SessionId alone signs the web app in; the other cookies change nothing.
SESSION_COOKIES = ("SessionId",)
COOKIE_DOMAIN = ".go.tradifyhq.com"
LOGIN_URL = "https://go.tradifyhq.com/"
# A final URL with one of these means the app signed the session out. Tradify answers 401 instead.
LOGGED_OUT_MARKERS: tuple[str, ...] = ()
# An answer with one of these asks you to sign in again before a sensitive action. Tradify has none.
RELOGIN_MARKERS: tuple[str, ...] = ()
# Paths a tool may only read: sign-in, sign-out, password and 2-Step Security calls of the web app.
# Any method but GET, HEAD or OPTIONS to one of them is refused before it leaves (core/account_guard.py).
ACCOUNT_PATHS = (r"^/api/Manage/",)
# REST routes live under this path, the same as on cotlet.dev.
API_PREFIX = "/api/v1/tradify"
# Prepended to the MCP server's instructions: where an agent starts.
AGENT_START = (
    "Start with list_jobs and list_customers: their job_id and customer_id are what get_job, create_job, "
    "create_quote and schedule_appointment take. list_quotes gives the quote_id for send_quote and "
    "create_invoice_from_quote, list_invoices the invoice_id for send_invoice and record_payment. "
    "Times are wall clock in the company's time zone."
)
