# Robinhood Trading (MCP) — Human-Gated Agentic Trading

Claude Code plugin that connects to **Robinhood's official agentic-trading MCP server**
(`https://agent.robinhood.com/mcp/trading`) and wraps it in the discipline this repo applies to
every high-stakes domain: deterministic gates, named human approval, and an auditable record.

> Robinhood opened its platform to AI agents in May 2026: a dedicated **Agentic account** the
> user funds separately, OAuth-only authentication, per-trade notifications, and in-app
> disconnect. This plugin is the client-side counterpart — it assumes those guardrails and adds
> its own.

## What's inside

```
robinhood-trading/
├── .mcp.json                          # bundled MCP registration (streamable HTTP + OAuth)
├── .claude-plugin/plugin.json
├── agents/cs-robinhood-trader.md      # risk-first execution persona
├── commands/cs-robinhood.md           # /cs:robinhood
└── skills/robinhood-trading/
    ├── SKILL.md                       # hard rules + the 9-step trading loop
    ├── scripts/
    │   ├── order_guard.py             # pre-trade risk gate (SEC 15c3-5 style)
    │   ├── portfolio_snapshot_analyzer.py  # weights, HHI, cash %, P/L, flags
    │   └── trade_journal.py           # propose → approve(named human) → place ledger
    ├── references/                    # MCP tool canon, guardrail canon, order lifecycle
    └── assets/sample_portfolio_snapshot.json
```

## The one design decision that matters

**The agent never decides to trade.** Every order passes three gates, in order:

1. `order_guard.py` — deterministic checks (budget, concentration, order type, rate, account).
   Best verdict possible: `CLEARED-FOR-HUMAN-CONFIRMATION`. There is no `APPROVED`.
2. `mcp__robinhood__review_equity_order` — Robinhood's own pre-trade review, surfaced verbatim.
3. **A human says yes to this specific order in this session**, and the journal records who.

`trade_journal.py place` exits non-zero if no named human approval precedes it. Unattended
loops, blanket pre-approvals, and "approved-by: Claude" are refused by design.

## Install

```bash
/plugin install robinhood-trading@claude-code-skills
```

First tool call opens Robinhood's OAuth flow. Prerequisites (done in the Robinhood app, not
here): primary account in good standing → open the Agentic account → fund it with only what the
agent may touch → leave trade notifications on.

## Not advice

Nothing in this plugin is investment advice. Equities trading involves risk of loss up to the
entire amount invested. AI-driven strategies can perform poorly, move fast, and be hard to stop
— which is why every step of this plugin slows them down.

## License

MIT (this plugin's code and docs). Robinhood, the Robinhood logo, and the agentic-trading
service are Robinhood Markets, Inc.'s — this plugin is an independent client integration, not
affiliated with or endorsed by Robinhood.
