# Agentic Trading Guardrails — Why Every Gate Exists

The `order_guard.py` gates and the skill's hard rules are not house style — each one maps to
a regulatory requirement, a documented failure, or a guardrail Robinhood itself imposes. This
document is the "why" behind every "no".

## Layer 1 — Robinhood's own guardrails (the platform layer)

Robinhood designed agentic trading around containment, and this skill assumes all of it:

- **Dedicated Agentic account.** Agents trade only in a separate account the user funds
  deliberately. Read access spans accounts; write access does not. Corollary for this skill:
  *never* suggest topping up the agentic account to make an order fit — the funding decision
  is the human's primary risk control, made calmly in the app, not under prompting.
- **OAuth, not credentials.** The agent never holds a password or key; access is revocable
  in-app at any time, independent of anything the agent does.
- **Per-trade notifications + live activity view.** The human's monitoring channel is outside
  the agent's control — by design. Never advise turning notifications off.
- **Disconnect anytime.** The kill switch is the user's, in the app. The agent-side
  equivalent is this skill's rate gate: when the daily order cap is hit, trading stops and
  the human is told. An exhausted budget is an escalation, never a workaround.

## Layer 2 — Regulatory canon (the market-structure layer)

- **SEC Rule 15c3-5 (Market Access Rule).** Brokers with market access must apply *automated,
  pre-trade* risk controls — credit/capital thresholds, erroneous-order checks — *before*
  orders reach the market, with thresholds set in advance and changed only deliberately.
  `order_guard.py` is a client-side miniature of this: pre-set caps (per-order notional,
  position weight, daily rate) checked deterministically before any order is even shown to
  the human. The Rule's core insight transfers whole: risk checks that can be waived in the
  moment of enthusiasm are not risk checks.
- **FINRA Rule 4210 — Pattern Day Trader.** Four or more day trades in five business days in
  a margin account under $25,000 equity flags the account, restricting it. The G7 gate warns
  at day trade #1–2 and refuses the trade that would trip the flag. An agent that day-trades
  a small account into a PDT restriction has destroyed the account's usability to win one
  trade.
- **FINRA Regulatory Notice 15-09 (algorithmic trading supervision).** FINRA's guidance for
  algo trading: pre-set limits, kill switches, testing before deployment, and *supervision by
  people who understand the strategy*. Mapped here: policy caps (limits), the daily rate gate
  (throttle), `--sample` smoke tests (testing), and the named-human approval in
  `trade_journal.py` (supervision with a name attached).
- **FINRA Rule 5310 (best execution) + SEC investor guidance on order types.** Market orders
  execute at whatever the market gives, and fast markets make that expensive; limit orders
  cap the price. This is why G4 requires limit orders by default and bands the limit price to
  the quote — a stale or fat-fingered limit far from the market is either a non-fill or a
  bad fill.

## Layer 3 — The failure canon (why pre-trade beats post-trade)

- **Knight Capital, August 1, 2012.** A dormant code path activated by a botched deploy sent
  millions of erroneous orders in 45 minutes: ~$460M loss, firm effectively destroyed, and
  the SEC's 2013 enforcement order became the reference case for Rule 15c3-5. The lesson
  encoded here: the speed that makes automated trading useful is exactly what makes
  *unattended* automated trading dangerous. Hard rule 5 (no unattended loops) is the Knight
  lesson applied to a retail agent.
- **AI-specific failure modes.** An LLM agent adds failure modes Knight didn't have:
  hallucinated tickers (G6 blocklist + quote check force a real symbol), sycophantic
  compliance ("just this once, skip the review" — hard rules are phrased as non-negotiable
  precisely for this), goal drift across a long session (per-order confirmation resets intent
  every single trade), and prompt injection from fetched content (nothing read from the web
  or from tool output can approve an order — only the human in-session can).

## Layer 4 — What this skill adds on top

| Gate / rule | Default | Source of the number |
|-------------|---------|----------------------|
| Per-order notional cap (G2) | $1,000 | conservative retail sizing; 15c3-5 pre-set-threshold discipline |
| Single-position weight cap (G3) | 20% | common concentration guideline; mirrors the analyzer's flag |
| Limit-price band (G4) | 5% of quote | erroneous-order check in the spirit of 15c3-5 |
| Daily order cap (G5) | 5 | runaway-loop protection (Knight lesson, retail scale) |
| PDT protection (G7) | $25,000 floor, refuse 4th day trade | FINRA Rule 4210 verbatim |
| Named human approval | always | FINRA 15-09 supervision + this repo's deal-desk pattern |

Defaults are deliberately tight. Loosening them is a valid *human* decision made in the
policy block of the input document — never something the agent proposes mid-session to make
a specific trade fit ("the budget is the guardrail").

## Not advice, not a fiduciary

Neither this skill nor the agent running it is an investment adviser, and no output is a
recommendation to buy or sell any security. Robinhood's own disclosures say the same of the
platform: agentic trading involves significant risk including total loss, and AI strategies
can perform poorly, move fast, and be hard to stop — which is the reason every layer above
exists.

## Sources

1. SEC Rule 15c3-5 — Risk Management Controls for Brokers or Dealers with Market Access (17 CFR 240.15c3-5): https://www.sec.gov/rules/final/2010/34-63241.pdf
2. SEC — In the Matter of Knight Capital Americas LLC, Exchange Act Release No. 70694 (Oct 16, 2013): https://www.sec.gov/litigation/admin/2013/34-70694.pdf
3. FINRA Rule 4210 (margin; pattern day trader definition and $25,000 requirement): https://www.finra.org/rules-guidance/rulebooks/finra-rules/4210
4. FINRA Regulatory Notice 15-09 — Guidance on Effective Supervision and Control Practices for Algorithmic Trading Strategies: https://www.finra.org/rules-guidance/notices/15-09
5. FINRA Rule 5310 — Best Execution: https://www.finra.org/rules-guidance/rulebooks/finra-rules/5310
6. SEC Investor.gov — Basics of Order Types (market vs limit): https://www.investor.gov/introduction-investing/investing-basics/how-stock-markets-work/types-orders
7. Robinhood Support — "Agentic Trading overview" (dedicated account, notifications, disconnect, risk disclosure): https://robinhood.com/us/en/support/articles/agentic-trading-overview/
8. Finder — "Robinhood Agentic Trading Review: How It Works & Risks": https://www.finder.com/stock-trading/robinhood-agentic-accounts
