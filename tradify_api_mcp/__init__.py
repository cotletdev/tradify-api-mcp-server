"""Self-hosted API and MCP server for one app (see app.py). Personal use only, see LICENSE.

From Python, without a server:

    from tradify_api_mcp import call
    customers = call("list_customers", search="smith")["customers"]
"""

from __future__ import annotations

import asyncio
from typing import Any

__version__ = "1.0.1"


def call(tool: str, args: dict[str, Any] | None = None, **kwargs: Any) -> Any:
    """Run one tool with the saved session and return its answer. Raises ToolError on failure."""
    from tradify_api_mcp.runner import Runner

    async def go() -> Any:
        runner = Runner()
        try:
            return await runner.run(tool, {**(args or {}), **kwargs})
        finally:
            await runner.close()

    return asyncio.run(go())
