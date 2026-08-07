# Finance Skills - Claude Code Guidance

This guide covers the 4 production-ready finance skill packages and their Python automation tools.

## Finance Skills Overview

**Available Skills:**
1. **financial-analyst/** - Financial statement analysis, ratio analysis, DCF valuation, budgeting, forecasting (4 Python tools)
2. **saas-metrics-coach/** - SaaS financial health: ARR, MRR, churn, CAC, LTV, NRR, Quick Ratio, 12-month projections (3 Python tools)
3. **business-investment-advisor/** - Investment thesis evaluation, ROI modeling, capital allocation guidance
4. **robinhood-trading/** (nested plugin) - Human-gated trading loop for Robinhood's official agentic-trading MCP server, bundled via `.mcp.json` (3 Python tools)

**Total Tools:** 10 Python automation tools, 8 knowledge bases, 6 templates

**Commands:** 3 (`/financial-health`, `/saas-health`, `/cs:robinhood`)

## Python Automation Tools

### 1. Ratio Calculator (`financial-analyst/scripts/ratio_calculator.py`)

**Purpose:** Calculate and interpret financial ratios from statement data

**Features:**
- Profitability ratios (ROE, ROA, Gross/Operating/Net Margin)
- Liquidity ratios (Current, Quick, Cash)
- Leverage ratios (Debt-to-Equity, Interest Coverage, DSCR)
- Efficiency ratios (Asset/Inventory/Receivables Turnover, DSO)
- Valuation ratios (P/E, P/B, P/S, EV/EBITDA, PEG)
- Built-in interpretation and benchmarking

**Usage:**
```bash
python financial-analyst/scripts/ratio_calculator.py financial_data.json
python financial-analyst/scripts/ratio_calculator.py financial_data.json --format json
```

### 2. DCF Valuation (`financial-analyst/scripts/dcf_valuation.py`)

**Purpose:** Discounted Cash Flow enterprise and equity valuation

**Features:**
- Revenue and cash flow projections
- WACC calculation (CAPM-based)
- Terminal value (perpetuity growth and exit multiple methods)
- Enterprise and equity value derivation
- Two-way sensitivity analysis
- No external dependencies (uses math/statistics)

**Usage:**
```bash
python financial-analyst/scripts/dcf_valuation.py valuation_data.json
python financial-analyst/scripts/dcf_valuation.py valuation_data.json --format json
```

### 3. Budget Variance Analyzer (`financial-analyst/scripts/budget_variance_analyzer.py`)

**Purpose:** Analyze actual vs budget vs prior year performance

**Features:**
- Variance calculation (actual vs budget, actual vs prior year)
- Materiality threshold filtering
- Favorable/unfavorable classification
- Department and category breakdown

**Usage:**
```bash
python financial-analyst/scripts/budget_variance_analyzer.py budget_data.json
python financial-analyst/scripts/budget_variance_analyzer.py budget_data.json --format json
```

### 4. Forecast Builder (`financial-analyst/scripts/forecast_builder.py`)

**Purpose:** Driver-based revenue forecasting and cash flow projection

**Features:**
- Driver-based revenue forecast model
- 13-week cash flow projection
- Scenario modeling (base/bull/bear)
- Trend analysis from historical data

**Usage:**
```bash
python financial-analyst/scripts/forecast_builder.py forecast_data.json
python financial-analyst/scripts/forecast_builder.py forecast_data.json --format json
```

## Robinhood Agentic Trading (robinhood-trading/, nested plugin)

Human-gated trading loop for Robinhood's official agentic-trading MCP server
(`https://agent.robinhood.com/mcp/trading`) — bundled `.mcp.json` (streamable HTTP, OAuth
handled by Claude Code, no env vars), same pattern as project-management's Atlassian MCP.
Canonical tool list: `robinhood-trading/skills/robinhood-trading/references/robinhood_mcp_tools.md`
— never invent tool names.

**Hard rules (binding):** explicit per-order in-session human confirmation (blanket
pre-approvals refused) · `review_equity_order` before every `place_equity_order` · no
unattended or scheduled trading · dedicated agentic account only · no investment advice.

```bash
cd robinhood-trading/skills/robinhood-trading

# Pre-trade risk gate (SEC 15c3-5 style). Best verdict: CLEARED-FOR-HUMAN-CONFIRMATION.
# Exit 0 cleared / 2 revise / 3 refuse — there is deliberately no APPROVED.
python3 scripts/order_guard.py order.json

# Portfolio analysis from saved MCP reads (weights, HHI, cash drag, unrealized P/L)
python3 scripts/portfolio_snapshot_analyzer.py snapshot.json

# Auditable ledger: propose -> approve (named human, agent-ish names refused) -> place
python3 scripts/trade_journal.py propose --order order.json --verdict CLEARED-FOR-HUMAN-CONFIRMATION
python3 scripts/trade_journal.py approve 1 --approved-by "Jane Doe"
python3 scripts/trade_journal.py place 1 --order-id RH-123456   # refuses without prior approval
```

Agent: `cs-robinhood-trader` · Command: `/cs:robinhood`

## Quality Standards

**All finance Python tools must:**
- Use standard library only (math, statistics, json, argparse)
- Support both JSON and human-readable output via `--format` flag
- Provide clear error messages for invalid input
- Return appropriate exit codes
- Process files locally (no API calls)
- Include argparse CLI with `--help` support

## Related Skills

- **C-Level:** Strategic financial decision-making -> `../c-level-advisor/`
- **Business & Growth:** Revenue operations, sales metrics -> `../business-growth/`
- **Product Team:** Budget allocation, RICE scoring -> `../product-team/`

---

**Last Updated:** August 7, 2026
**Skills Deployed:** 4/4 finance skill packages production-ready (robinhood-trading is a nested plugin)
**Total Tools:** 10 Python automation tools
**Commands:** /financial-health, /saas-health, /cs:robinhood
