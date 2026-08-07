---
name: "cs-robinhood"
description: "/cs:robinhood — human-gated trading session on Robinhood's official agentic-trading MCP. Snapshot + portfolio analysis, deterministic pre-trade gate, Robinhood's own order review, explicit per-order confirmation, auditable journal. Never auto-places, never trades unattended, never gives advice."
---

# /cs:robinhood — Human-Gated Robinhood Trading Session

**Command:** `/cs:robinhood`

The `cs-robinhood-trader` persona runs a trading session against
`https://agent.robinhood.com/mcp/trading` (bundled `.mcp.json`, OAuth in the browser) with
the full 9-step lifecycle from the `robinhood-trading` skill.

## When to Run

- "Check my Robinhood portfolio" / "how concentrated am I?"
- "Buy/sell N shares of X on Robinhood" — with you confirming each order
- "Rebalance my agentic account toward these targets" — proposed as N individually
  confirmed orders
- "Cancel my open order" / "what filled today?"

## When NOT to Run

- You want the agent to trade without you present (refused — hard rule 5)
- You want a prediction or a recommendation ("should I buy X?" gets analysis, not advice)
- Financial statement / SaaS metrics work → `/financial-health`, `/saas-health`
- Investment thesis evaluation → `finance/business-investment-advisor`

## What You Get

1. **Session intake** — 5 forcing questions (account scope, goal, caps, order type,
   notifications), one per turn, each with a recommended answer.
2. **Snapshot analysis** — weights, HHI concentration verdict, cash %, unrealized P/L,
   flags (CONCENTRATION / CASH-DRAG / LOSS-RUNNER / REVIEW-WINNER).
3. **Per order:** the gate verdict (`CLEARED-FOR-HUMAN-CONFIRMATION` / `REVISE` /
   `REFUSE` with named gates G1–G7), Robinhood's own `review_equity_order` output verbatim,
   and one AskUserQuestion confirmation. Your "yes" covers exactly that order.
4. **An auditable journal** — every proposal, who approved it, the Robinhood order id, and
   the terminal state, reconciled against `get_equity_orders` before the session closes.

## Pre-flight gates (refuse with the reason, offer the fix)

1. MCP server not connected / OAuth pending → connect first; never simulate tool output.
2. No dedicated agentic account visible → open/fund it in the Robinhood app first.
3. Request is for unattended or scheduled trading → refuse; offer monitor-and-alert.
4. Request is for advice/predictions → refuse; offer analysis.

## Trigger Phrases (auto-invoke without /cs:)

- "trade on Robinhood" / "my Robinhood agentic account"
- "buy … on Robinhood" / "sell … on Robinhood"
- "check my Robinhood portfolio" / "robinhood rebalance"
