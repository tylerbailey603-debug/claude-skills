#!/usr/bin/env python3
"""order_guard.py — deterministic pre-trade risk gate for the Robinhood trading loop.

Runs SEC Rule 15c3-5-style pre-trade checks on a proposed equity order BEFORE it is
shown to the human for confirmation. The best verdict this tool can issue is
CLEARED-FOR-HUMAN-CONFIRMATION — it never approves an order, because approval is a
human's job. There is deliberately no flag, env var, or policy setting that skips
the human.

Gates (defaults overridable via the input's "policy" block):
  G1 ACCOUNT        order must target the dedicated agentic account        -> REFUSE
  G2 BUDGET         notional <= max_order_notional AND <= buying power;
                    sells limited to shares actually held (no shorting)    -> REVISE/REFUSE
  G3 CONCENTRATION  post-trade position weight <= max_position_pct         -> REVISE
  G4 ORDER TYPE     limit orders required (unless policy allows market);
                    limit price within limit_price_band_pct of the quote   -> REVISE
  G5 RATE           orders_today < max_orders_per_day (loop protection)    -> REFUSE
  G6 BLOCKLIST      symbol not on the policy blocklist                     -> REFUSE
  G7 PDT            pattern-day-trade protection under $25k equity         -> WARN/REFUSE

Verdicts and exit codes:
  0  CLEARED-FOR-HUMAN-CONFIRMATION  (all gates pass; warnings may be attached)
  2  REVISE                          (fixable: resize, reprice, or retype the order)
  3  REFUSE                          (drop the order; do not present it to the human)
  1  input/validation error

Usage:
  python3 order_guard.py order.json
  python3 order_guard.py order.json --format json
  python3 order_guard.py --sample          # print a sample input document
  python3 order_guard.py --sample | python3 order_guard.py -

Stdlib only. No network calls. Not investment advice.
"""

import argparse
import json
import sys

DEFAULT_POLICY = {
    "max_order_notional": 1000.0,
    "max_position_pct": 20.0,
    "max_orders_per_day": 5,
    "allow_market_orders": False,
    "limit_price_band_pct": 5.0,
    "symbol_blocklist": [],
    "pdt_equity_floor": 25000.0,
}

SAMPLE = {
    "order": {
        "account_type": "agentic",
        "symbol": "AAPL",
        "side": "buy",
        "quantity": 4,
        "order_type": "limit",
        "limit_price": 210.50,
        "time_in_force": "day",
    },
    "quote": {"symbol": "AAPL", "last_price": 209.80},
    "account": {
        "type": "agentic",
        "equity": 10000.0,
        "cash": 5000.0,
        "buying_power": 5000.0,
        "positions": [{"symbol": "AAPL", "quantity": 3, "market_value": 630.0}],
    },
    "history": {"orders_today": 1, "day_trades_last_5_days": 0, "bought_today": []},
    "policy": {
        "max_order_notional": 1000.0,
        "max_position_pct": 20.0,
        "max_orders_per_day": 5,
        "allow_market_orders": False,
        "limit_price_band_pct": 5.0,
        "symbol_blocklist": [],
    },
}

CLEARED = "CLEARED-FOR-HUMAN-CONFIRMATION"
REVISE = "REVISE"
REFUSE = "REFUSE"

_SEVERITY = {CLEARED: 0, REVISE: 1, REFUSE: 2}
_EXIT = {CLEARED: 0, REVISE: 2, REFUSE: 3}


def _fail(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def _num(value, name):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        _fail(f"{name} must be a non-negative number, got {value!r}")
    return float(value)


def evaluate(doc):
    order = doc.get("order")
    account = doc.get("account")
    if not isinstance(order, dict) or not isinstance(account, dict):
        _fail('input must contain "order" and "account" objects (see --sample)')

    quote = doc.get("quote") or {}
    history = doc.get("history") or {}
    policy = dict(DEFAULT_POLICY)
    policy.update(doc.get("policy") or {})

    symbol = str(order.get("symbol", "")).upper().strip()
    side = str(order.get("side", "")).lower().strip()
    order_type = str(order.get("order_type", "")).lower().strip()
    if not symbol:
        _fail("order.symbol is required")
    if side not in ("buy", "sell"):
        _fail('order.side must be "buy" or "sell"')
    if order_type not in ("limit", "market"):
        _fail('order.order_type must be "limit" or "market"')

    quantity = _num(order.get("quantity", 0), "order.quantity")
    if quantity <= 0:
        _fail("order.quantity must be > 0")

    limit_price = order.get("limit_price")
    last_price = quote.get("last_price")
    if order_type == "limit":
        limit_price = _num(limit_price if limit_price is not None else -1, "order.limit_price")
    if last_price is not None:
        last_price = _num(last_price, "quote.last_price")

    price_basis = limit_price if order_type == "limit" else last_price
    if price_basis is None:
        _fail("market orders need quote.last_price to size the notional check")
    notional = quantity * price_basis

    equity = _num(account.get("equity", 0), "account.equity")
    buying_power = _num(account.get("buying_power", account.get("cash", 0)), "account.buying_power")
    positions = {
        str(p.get("symbol", "")).upper(): p
        for p in account.get("positions", [])
        if isinstance(p, dict)
    }

    findings = []  # (gate, verdict, message)
    warnings = []

    # G1 ACCOUNT — dedicated agentic account only.
    if str(account.get("type", "")).lower() != "agentic":
        findings.append(("G1-ACCOUNT", REFUSE,
                         f'account.type is "{account.get("type")}" — orders may only target the '
                         "dedicated agentic account. Do not work around this by retyping the account."))

    # G2 BUDGET — per-order cap, buying power, and no shorting.
    cap = float(policy["max_order_notional"])
    if notional > cap:
        findings.append(("G2-BUDGET", REVISE,
                         f"order notional ${notional:,.2f} exceeds the per-order cap ${cap:,.2f} — "
                         "reduce quantity or split across sessions (not across rapid-fire orders)."))
    if side == "buy" and notional > buying_power:
        findings.append(("G2-BUDGET", REVISE,
                         f"order notional ${notional:,.2f} exceeds buying power ${buying_power:,.2f}. "
                         "Resize the order. Never suggest funding the account to fit an order — "
                         "the funded budget IS the guardrail."))
    if side == "sell":
        held = _num(positions.get(symbol, {}).get("quantity", 0), "position.quantity")
        if quantity > held:
            findings.append(("G2-BUDGET", REFUSE,
                             f"selling {quantity:g} {symbol} but only {held:g} held — short selling "
                             "is not supported in this loop."))

    # G3 CONCENTRATION — post-trade position weight vs equity.
    if side == "buy" and equity > 0:
        existing_mv = _num(positions.get(symbol, {}).get("market_value", 0), "position.market_value")
        post_weight = (existing_mv + notional) / equity * 100.0
        max_pct = float(policy["max_position_pct"])
        if post_weight > max_pct:
            findings.append(("G3-CONCENTRATION", REVISE,
                             f"post-trade {symbol} weight {post_weight:.1f}% exceeds the "
                             f"{max_pct:.0f}% single-position cap — reduce quantity."))

    # G4 ORDER TYPE — limit discipline and price band.
    if order_type == "market" and not policy["allow_market_orders"]:
        findings.append(("G4-ORDER-TYPE", REVISE,
                         "market orders are disabled by policy (slippage risk) — convert to a "
                         "limit order priced near the quote."))
    if order_type == "limit" and last_price:
        band = float(policy["limit_price_band_pct"])
        drift = abs(limit_price - last_price) / last_price * 100.0
        if drift > band:
            findings.append(("G4-ORDER-TYPE", REVISE,
                             f"limit price ${limit_price:,.2f} is {drift:.1f}% away from the last "
                             f"quote ${last_price:,.2f} (band: {band:.0f}%) — reprice or refresh "
                             "the quote."))

    # G5 RATE — loop protection.
    orders_today = int(history.get("orders_today", 0))
    max_daily = int(policy["max_orders_per_day"])
    if orders_today >= max_daily:
        findings.append(("G5-RATE", REFUSE,
                         f"{orders_today} orders already placed today (cap: {max_daily}) — stop "
                         "trading for the day and report to the human. An exhausted budget is an "
                         "escalation, never a workaround."))

    # G6 BLOCKLIST.
    blocklist = {str(s).upper() for s in policy.get("symbol_blocklist", [])}
    if symbol in blocklist:
        findings.append(("G6-BLOCKLIST", REFUSE,
                         f"{symbol} is on the policy blocklist."))

    # G7 PDT — pattern-day-trade protection (FINRA Rule 4210).
    pdt_floor = float(policy["pdt_equity_floor"])
    day_trades = int(history.get("day_trades_last_5_days", 0))
    bought_today = {str(s).upper() for s in history.get("bought_today", [])}
    would_day_trade = side == "sell" and symbol in bought_today
    if equity < pdt_floor:
        if would_day_trade and day_trades >= 3:
            findings.append(("G7-PDT", REFUSE,
                             f"this sell would be day trade #{day_trades + 1} in 5 business days "
                             f"with equity under ${pdt_floor:,.0f} — it would flag the account as a "
                             "pattern day trader (FINRA Rule 4210)."))
        elif would_day_trade:
            warnings.append(f"G7-PDT: this sell closes a position opened today — day trade "
                            f"{day_trades + 1} of the 3 allowed per 5 business days under "
                            f"${pdt_floor:,.0f} equity.")

    verdict = CLEARED
    for _, v, _ in findings:
        if _SEVERITY[v] > _SEVERITY[verdict]:
            verdict = v

    return {
        "verdict": verdict,
        "order": {
            "symbol": symbol, "side": side, "quantity": quantity,
            "order_type": order_type, "limit_price": limit_price,
            "notional": round(notional, 2),
            "time_in_force": order.get("time_in_force", "day"),
        },
        "findings": [
            {"gate": g, "verdict": v, "message": m} for g, v, m in findings
        ],
        "warnings": warnings,
        "policy": policy,
        "note": ("This is a pre-trade gate, not an approval. A named human must confirm this "
                 "exact order in-session before placement. Not investment advice."),
    }


def render_human(result):
    lines = []
    o = result["order"]
    lines.append("ORDER GUARD — pre-trade gate")
    lines.append("=" * 60)
    lines.append(f"  {o['side'].upper()} {o['quantity']:g} {o['symbol']} "
                 f"({o['order_type']}"
                 + (f" @ ${o['limit_price']:,.2f}" if o["limit_price"] else "")
                 + f", {o['time_in_force']}) — notional ${o['notional']:,.2f}")
    lines.append("-" * 60)
    if result["findings"]:
        for f in result["findings"]:
            lines.append(f"  [{f['verdict']:6s}] {f['gate']}: {f['message']}")
    else:
        lines.append("  all gates passed")
    for w in result["warnings"]:
        lines.append(f"  [WARN  ] {w}")
    lines.append("-" * 60)
    lines.append(f"VERDICT: {result['verdict']}")
    lines.append("")
    lines.append(result["note"])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Deterministic pre-trade risk gate for the Robinhood trading loop. "
                    "Best verdict: CLEARED-FOR-HUMAN-CONFIRMATION — never an approval.")
    parser.add_argument("input", nargs="?",
                        help="path to the order document (JSON), or '-' for stdin")
    parser.add_argument("--format", choices=["human", "json"], default="human")
    parser.add_argument("--sample", action="store_true",
                        help="print a sample input document and exit")
    args = parser.parse_args()

    if args.sample:
        print(json.dumps(SAMPLE, indent=2))
        return 0

    if not args.input:
        parser.error("input file required (or --sample)")

    try:
        raw = sys.stdin.read() if args.input == "-" else open(args.input, encoding="utf-8").read()
        doc = json.loads(raw)
    except OSError as exc:
        _fail(f"cannot read {args.input}: {exc}")
    except json.JSONDecodeError as exc:
        _fail(f"invalid JSON: {exc}")

    result = evaluate(doc)
    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(render_human(result))
    return _EXIT[result["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
