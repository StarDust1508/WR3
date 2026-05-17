"""wr3 MCP server — Model Context Protocol tools for AI agents.

Exposes the wr3 audit pipeline as MCP tools so external agents (e.g. the
user's Hermes assistant, Claude Desktop, Cursor) can run scans, fetch
incidents, and search the audit history without writing HTTP code.

Wire it into an MCP client config like:

    {
      "mcpServers": {
        "wr3": {
          "command": "uv",
          "args": ["run", "wr3-mcp"],
          "env": {
            "WR3_API_URL": "https://wr3.bigmandmitriy777.workers.dev"
          }
        }
      }
    }
"""

from wr3_mcp.server import run

__all__ = ["run"]
