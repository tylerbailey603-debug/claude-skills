#!/usr/bin/env python3
"""portfolio_snapshot_analyzer.py — analyze a saved Robinhood MCP portfolio snapshot.

Takes the JSON you saved from `mcp__robinhood__get_portfolio` +
`mcp__robinhood__get_equity_positions` (merged into one document, shape below) and
computes deterministic portfolio health metrics. Follows the repo's snapshot-bridge
pattern (like project-management's jira_snapshot_bridge.py): the MCP read happens in
the agent, the math happens here, offline and reproducibly.

Metrics:
  - per-position market value, weight, unrealized P/L (when avg_cost present)
  - cash weight and buying power
  - HHI concentration index over invested weights (0-10000; <1500 diversified,
    1500-2500 moderate, >2500 concentrated — DOJ/FTC merger-guideline bands)
  - flags: CONCENTRATION (position > max weight), CASH-DRAG (cash > threshold),
    LOSS-RUNNER (unrealized loss >= 20%), REVIEW-WINNER (unrealized gain >= 50%)

Verdicts: DIVERSIFIED / MODERATE-CONCENTRATION / CONCENTRATED (from HHI), plus flags.
Analysis only — no buy/sell recommendation is ever emitted. Not investment advice.

Exit codes: 0 analyzed, 1 input error.

Usage:
  python3 portfolio_snapshot_analyzer.py snapshot.json
  python3 portfolio_snapshot_analyzer.py snapshot.json --format json
  python3 portfolio_snapshot_analyzer.py --sample        # print a sample snapshot
  python3 portfolio_snapshot_analyzer.py --sample | python3 portfolio_snapshot_analyzer.py -

Stdlib only. No network calls.
"""

import argparse
import json
import sys

SAMPLE = {
    "as_of": "2026-08-07",
    "account": {"type": "agentic", "cash": 1200.0, "buying_power": 1200.0},
    "positions": [
        {"symbol": "AAPL", "quantity": 3, "avg_cost": 195.00, "price": 210.00},
        {"symbol": "MSFT", "quantity": 2, "avg_cost": 470.00, "price": 452.00},
        {"symbol": "VOO", "quantity": 4, "avg_cost": 520.00, "price": 561.00},
        {"symbol": "SNAP", "quantity": 60, "avg_cost": 14.50, "price": 9.80},
    ],
}

DEFAULT_MAX_POSITION_PCT = 20.0
DEFAULT_CASH_DRAG_PCT = 30.0


def _fail(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def _num(value, name, allow_zero=True):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        _fail(f"{name} must be a number, got {value!r}")
    if value < 0 or (not allow_zero and value == 0):
        _fail(f"{name} must be positive, got {value!r}")
    return float(value)


def analyze(doc, max_position_pct=DEFAULT_MAX_POSITION_PCT,
            cash_drag_pct=DEFAULT_CASH_DRAG_PCT):
    account = doc.get("account") or {}
    raw_positions = doc.get("positions")
    if not isinstance(raw_positions, list) or not raw_positions:
        _fail('input must contain a non-empty "positions" array (see --sample)')

    cash = _num(account.get("cash", 0), "account.cash")

    positions = []
    for i, p in enumerate(raw_positions):
        if not isinstance(p, dict):
            _fail(f"positions[{i}] must be an object")
        symbol = str(p.get("symbol", "")).upper().strip()
        if not symbol:
            _fail(f"positions[{i}].symbol is required")
        quantity = _num(p.get("quantity", 0), f"positions[{i}].quantity", allow_zero=False)
        if "market_value" in p:
            mv = _num(p["market_value"], f"positions[{i}].market_value")
            price = mv / quantity
        elif "price" in p:
            price = _num(p["price"], f"positions[{i}].price")
            mv = price * quantity
        else:
            _fail(f"positions[{i}] needs either market_value or price")
        avg_cost = p.get("avg_cost")
        if avg_cost is not None:
            avg_cost = _num(avg_cost, f"positions[{i}].avg_cost")
        positions.append({"symbol": symbol, "quantity": quantity, "price": price,
                          "market_value": mv, "avg_cost": avg_cost})

    invested = sum(p["market_value"] for p in positions)
    total = invested + cash
    if total <= 0:
        _fail("portfolio total value is zero")

    hhi = 0.0
    flags = []
    for p in positions:
        p["weight_pct"] = round(p["market_value"] / total * 100.0, 2)
        invested_weight = p["market_value"] / invested if invested else 0.0
        hhi += (invested_weight * 100.0) ** 2
        if p["avg_cost"]:
            pl = (p["price"] - p["avg_cost"]) * p["quantity"]
            pl_pct = (p["price"] - p["avg_cost"]) / p["avg_cost"] * 100.0
            p["unrealized_pl"] = round(pl, 2)
            p["unrealized_pl_pct"] = round(pl_pct, 2)
            if pl_pct <= -20.0:
                flags.append({"flag": "LOSS-RUNNER", "symbol": p["symbol"],
                              "detail": f"unrealized loss {pl_pct:.1f}% — surface it; the human "
                                        "decides what, if anything, to do."})
            elif pl_pct >= 50.0:
                flags.append({"flag": "REVIEW-WINNER", "symbol": p["symbol"],
                              "detail": f"unrealized gain {pl_pct:.1f}% — weight may have drifted "
                                        "from the human's stated targets."})
        else:
            p["unrealized_pl"] = None
            p["unrealized_pl_pct"] = None
        if p["weight_pct"] > max_position_pct:
            flags.append({"flag": "CONCENTRATION", "symbol": p["symbol"],
                          "detail": f"{p['weight_pct']:.1f}% of the account exceeds the "
                                    f"{max_position_pct:.0f}% single-position guideline."})

    cash_pct = round(cash / total * 100.0, 2)
    if cash_pct > cash_drag_pct:
        flags.append({"flag": "CASH-DRAG", "symbol": "-",
                      "detail": f"cash is {cash_pct:.1f}% of the account — idle by design or "
                                "drift? A question for the human, not a trade signal."})

    hhi = round(hhi, 0)
    if hhi < 1500:
        verdict = "DIVERSIFIED"
    elif hhi <= 2500:
        verdict = "MODERATE-CONCENTRATION"
    else:
        verdict = "CONCENTRATED"

    positions.sort(key=lambda p: p["market_value"], reverse=True)
    return {
        "as_of": doc.get("as_of"),
        "verdict": verdict,
        "hhi": hhi,
        "totals": {
            "total_value": round(total, 2),
            "invested": round(invested, 2),
            "cash": round(cash, 2),
            "cash_pct": cash_pct,
            "positions": len(positions),
        },
        "positions": positions,
        "flags": flags,
        "note": ("Analysis only — no recommendation is implied by any metric or flag. "
                 "Not investment advice."),
    }


def render_human(result):
    lines = []
    lines.append("PORTFOLIO SNAPSHOT" + (f" — as of {result['as_of']}" if result["as_of"] else ""))
    lines.append("=" * 68)
    t = result["totals"]
    lines.append(f"  total ${t['total_value']:,.2f}  |  invested ${t['invested']:,.2f}  |  "
                 f"cash ${t['cash']:,.2f} ({t['cash_pct']:.1f}%)")
    lines.append(f"  HHI {result['hhi']:.0f}  ->  {result['verdict']}")
    lines.append("-" * 68)
    lines.append(f"  {'symbol':<8}{'qty':>8}{'value':>12}{'weight':>9}{'unrl P/L':>12}")
    for p in result["positions"]:
        pl = (f"{p['unrealized_pl_pct']:+.1f}%" if p["unrealized_pl_pct"] is not None else "n/a")
        lines.append(f"  {p['symbol']:<8}{p['quantity']:>8g}{p['market_value']:>12,.2f}"
                     f"{p['weight_pct']:>8.1f}%{pl:>12}")
    if result["flags"]:
        lines.append("-" * 68)
        for f in result["flags"]:
            lines.append(f"  [{f['flag']}] {f['symbol']}: {f['detail']}")
    lines.append("-" * 68)
    lines.append(result["note"])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze a saved Robinhood MCP portfolio snapshot: weights, HHI "
                    "concentration, cash drag, unrealized P/L. Analysis only, never advice.")
    parser.add_argument("input", nargs="?",
                        help="path to the snapshot JSON, or '-' for stdin")
    parser.add_argument("--format", choices=["human", "json"], default="human")
    parser.add_argument("--max-position-pct", type=float, default=DEFAULT_MAX_POSITION_PCT,
                        help="single-position weight guideline (default: 20)")
    parser.add_argument("--cash-drag-pct", type=float, default=DEFAULT_CASH_DRAG_PCT,
                        help="cash weight above which CASH-DRAG is flagged (default: 30)")
    parser.add_argument("--sample", action="store_true",
                        help="print a sample snapshot document and exit")
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

    result = analyze(doc, args.max_position_pct, args.cash_drag_pct)
    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(render_human(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
