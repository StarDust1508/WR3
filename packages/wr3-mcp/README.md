# wr3-mcp

MCP server exposing the **wr3** smart-contract audit platform as tools any AI agent can call directly — Claude Desktop, Cursor, the user's Hermes agent, etc.

Sits alongside other domain MCP servers (e.g. `Equibles` for equities, `playwright-mcp` for browsers) so a single agent can pull from all of them in one conversation.

## Tools

| Tool | Description |
|---|---|
| `list_recent_incidents` | Live exploit feed — Rekt News, SlowMist, DefiLlama, deduplicated by semantic similarity. |
| `list_public_scans` | Public leaderboard of completed audits, sorted by score. |
| `get_public_stats` | Aggregate platform stats. |
| `get_scan` | Full audit report by id — findings, axes breakdown, GoPlus/Solana metadata. |
| `scan_contract` | Start a NEW audit (30-120 seconds). Auto-fetches verified source on EVM; pass `source_code` for Solana. |
| `get_subscription_plans` | Stars-priced plans catalog. |

Every tool is read-only safe except `scan_contract`, which kicks off real LLM work and consumes the calling user's tier quota.

## Install

```bash
cd packages/wr3-mcp
uv sync
```

## Configure an MCP client

Claude Desktop / Cursor / Hermes — add to the MCP servers config:

```json
{
  "mcpServers": {
    "wr3": {
      "command": "uv",
      "args": ["--directory", "/path/to/wr3/packages/wr3-mcp", "run", "wr3-mcp"],
      "env": {
        "WR3_API_URL": "https://wr3.bigmandmitriy777.workers.dev/api"
      }
    }
  }
}
```

- `WR3_API_URL` defaults to the public CF Workers URL. For self-hosted, point at your FastAPI origin directly (omit `/api`).
- `WR3_AUTH_TOKEN` (optional) — Bearer JWT for owner-scoped tools. Get one from `POST /v1/auth/tg/login` after a Telegram WebApp login.

## Try it from the agent

```
> аудитни контракт 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48 на ethereum
[hermes → wr3-mcp.scan_contract(address, network)]
```

Agent receives the markdown-rendered scan report and continues the conversation around it.

## License

MIT.
