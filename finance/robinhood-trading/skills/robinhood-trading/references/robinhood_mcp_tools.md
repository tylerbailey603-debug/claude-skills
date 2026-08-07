# Robinhood Trading MCP — Canonical Tool Reference

The single source of truth for what the Robinhood agentic-trading MCP server at
`https://agent.robinhood.com/mcp/trading` can and cannot do from this skill. Modeled on
`project-management/references/atlassian-mcp-tools.md`: **never invent tool names** — if a
capability is not in the connected server's live tool listing, it is not available via MCP,
full stop. The live listing always wins over this document.

## The service in one paragraph

Robinhood opened its platform to AI agents on May 27, 2026 ("Robinhood is Now Open to
Agents"): a user opens a dedicated **Agentic account** — separate from their primary
individual investing account — funds it with only the money an agent may trade, and connects
any MCP-capable agent (Claude, ChatGPT, Codex, Cursor, Grok) by pasting one URL. The server
authenticates via **OAuth in Robinhood's own login flow** — the agent never sees a password or
API key. Robinhood's guardrails: trading is restricted to the dedicated account, every trade
generates a notification, activity is visible in the app in real time, and the user can
disconnect the agent from the app at any moment. The beta launched with **equities only**;
Robinhood announced expansion (crypto reported July 2026; options, event contracts, and
futures "coming soon"). Treat asset-class availability as a live question — check the tool
listing, not this file's snapshot.

## Connection

Bundled in this plugin's `.mcp.json` (streamable HTTP):

```json
{
  "mcpServers": {
    "robinhood": {
      "type": "http",
      "url": "https://agent.robinhood.com/mcp/trading"
    }
  }
}
```

Tools surface as `mcp__robinhood__<toolName>`. First call triggers the OAuth flow in the
browser. If the server is not connected, say so and stop — never simulate tool output.

## Reported tool surface (equities beta, as of August 2026)

| Group | Tool | What it does | Gate |
|-------|------|--------------|------|
| Read | `get_accounts` | List accounts visible to the connection (read spans accounts; **write never does**) | — |
| Read | `get_portfolio` | Portfolio summary: equity, cash, buying power | — |
| Read | `get_equity_positions` | Open positions with quantities and values | — |
| Read | `get_equity_quotes` | Quotes for one or more symbols | — |
| Read | `get_equity_orders` | Order history and open-order status | — |
| Read | `search` | Symbol / instrument search | — |
| Watchlist | `get_watchlists` | List watchlists | — |
| Watchlist | `add_to_watchlist` | Add symbols to a watchlist | — |
| Watchlist | `update_watchlist` | Rename / reorder / remove entries | — |
| **Trade** | `review_equity_order` | **Robinhood's own pre-trade review**: warnings + estimated cost, no order placed | run before every place |
| **Trade** | `place_equity_order` | Places the order in the agentic account | hard rules 1–4 |
| **Trade** | `cancel_equity_order` | Cancels an open order | journal the cancel |

Read and watchlist tools may be called freely. The three trade tools are gated by the
skill's hard rules: `order_guard.py` verdict → journal `propose` → `review_equity_order`
surfaced to the human → explicit per-order confirmation → journal `approve` (named human) →
`place_equity_order` → journal `place`.

## NOT available via MCP

Do not attempt, simulate, or promise any of the following — they are account-level actions
that belong in the Robinhood app, or capabilities the server does not expose:

- Opening, closing, or funding accounts; ACH/wire transfers; moving money between accounts
- Margin changes, options approval levels, account settings, personal data
- Multi-leg options strategies, futures, event contracts (single-leg options and crypto:
  check the live listing — rollout was announced but availability varies)
- Short selling (and this skill's `order_guard.py` refuses sells beyond shares held anyway)
- Fractional-share behavior, extended-hours sessions, and order-type variants beyond what
  `review_equity_order` accepts — let the review call be the authority and surface its answer

If the user asks for any of these, name the boundary and point at the Robinhood app.

## Failure and staleness discipline

- **Tool listing drift:** Robinhood iterates on the beta. On any `unknown tool` error,
  re-read the live listing and update the plan — do not retry a name from this file.
- **OAuth expiry:** a 401/auth error means the user must re-authenticate in the browser;
  never ask for credentials in chat.
- **Partial reads:** if `get_portfolio` succeeds but `get_equity_positions` fails, do not
  guess positions — the snapshot analyzer needs both or neither.
- **Quotes are delayed truth:** treat quotes as indicative; `review_equity_order`'s estimated
  cost is the number the human confirms against.

## Sources

1. Robinhood Newsroom — "Robinhood is Now Open to Agents" (May 27, 2026): https://robinhood.com/us/en/newsroom/robinhood-is-now-open-to-agents/
2. Robinhood — Agentic Trading product page: https://robinhood.com/us/en/agentic-trading/
3. Robinhood Support — "Agentic Trading overview": https://robinhood.com/us/en/support/articles/agentic-trading-overview/
4. TechCrunch — "Robinhood now lets your AI agents trade stocks" (May 27, 2026): https://techcrunch.com/2026/05/27/robinhood-now-lets-your-ai-agents-trade-stocks/
5. CNBC — "Your AI agent can now trade for you on Robinhood" (May 27, 2026): https://www.cnbc.com/2026/05/27/your-ai-agent-can-now-trade-for-you-on-robinhood-and-buy-stuff-with-your-credit-card-too.html
6. SecProve — "agent.robinhood.com/mcp/trading — the Robinhood Trading MCP URL, Explained": https://secprove.com/trading-agent-safety/robinhood-trading-mcp-url
7. Genfinity — "Robinhood Agentic Trading Opens to Crypto With MCP-Based AI Agent Support" (July 21, 2026): https://genfinity.io/2026/07/21/robinhood-agentic-trading-crypto-ai-agents/
8. Model Context Protocol specification (transports, OAuth): https://modelcontextprotocol.io/specification
