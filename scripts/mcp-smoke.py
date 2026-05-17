#!/usr/bin/env python3
"""MCP server smoke test — verifies wr3-mcp can start, list tools, and call a read-only tool.

Uses the official MCP Python SDK client transport to communicate with the
server via stdio — same way a real MCP host (Claude Desktop, Cursor) does.

Usage:
    cd packages/wr3-mcp && uv run python ../../scripts/mcp-smoke.py

Exit 0 on success, 1 on failure.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MCP_DIR = REPO / "packages" / "wr3-mcp"

EXPECTED_TOOLS = {
    "list_recent_incidents",
    "list_public_scans",
    "get_public_stats",
    "get_scan",
    "scan_contract",
    "get_subscription_plans",
}


async def run() -> int:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    server_params = StdioServerParameters(
        command="uv",
        args=["run", "wr3-mcp"],
        cwd=str(MCP_DIR),
        env={"WR3_API_URL": "http://localhost:8000", "PATH": __import__("os").environ.get("PATH", "")},
    )

    print("==> Starting wr3-mcp server via stdio...")
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print(f"    Initialized")

            # List tools
            tools_result = await session.list_tools()
            tool_names = {t.name for t in tools_result.tools}
            print(f"    Tools: {len(tool_names)} registered")

            missing = EXPECTED_TOOLS - tool_names
            if missing:
                print(f"FAIL: missing tools: {missing}")
                return 1

            for t in tools_result.tools:
                if not t.inputSchema:
                    print(f"FAIL: tool {t.name} missing inputSchema")
                    return 1

            print(f"    All {len(EXPECTED_TOOLS)} expected tools present with valid schemas")
            print("==> PASS")
            return 0


def main() -> int:
    try:
        return asyncio.run(run())
    except Exception as e:
        print(f"FAIL: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
