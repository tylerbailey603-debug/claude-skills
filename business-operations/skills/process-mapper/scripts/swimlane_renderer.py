#!/usr/bin/env python3
"""swimlane_renderer.py

Render a documented business process as a visual swim-lane diagram.

Two output formats:
  --output html     Single self-contained HTML file (inline SVG + CSS, no
                    external requests). Opens offline, prints to PDF.
  --output mermaid  Mermaid `flowchart LR` with one subgraph per lane, for
                    GitHub / Notion / markdown previews.

The HTML view stacks two canons on one page:
  - a BPMN-style swim-lane (one row per owner) so cross-functional handoffs
    are visible as vertical hops, and
  - a Lean value-stream time ribbon underneath, where each stage's width is
    its literal share of total P50, so the reader sees where elapsed time
    actually goes rather than where the boxes are.

The bottleneck highlight is not computed here: it is imported from
`bottleneck_detector.detect()` so the diagram can never disagree with the
ranked findings the other tools report.

Stdlib only. Invalid input exits 3; see `process_model.py` for the schema.
"""
from __future__ import annotations

import argparse
import html
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from process_model import resolve  # noqa: E402
from bottleneck_detector import PROFILES as BOTTLENECK_PROFILES, detect  # noqa: E402
from cycle_time_analyzer import analyze  # noqa: E402


# --- Layout constants (px). Fixed geometry keeps the SVG deterministic. ---
LANE_LABEL_W = 200
BOX_W = 196
BOX_H = 78
GAP_X = 52
LANE_PAD = 16
LANE_H = BOX_H + 2 * LANE_PAD
MARGIN = 28
RIBBON_H = 108

TYPE_LABEL = {
    "value-add": "Value-add",
    "wait": "Wait",
    "rework": "Rework",
}
TYPE_GLYPH = {
    "value-add": "▶",   # ▶
    "wait": "⏸",        # ⏸
    "rework": "↺",      # ↺
}


def fmt_duration(minutes: float) -> str:
    """Human-readable duration. Business processes span minutes to weeks."""
    if minutes < 60:
        return f"{minutes:.0f}m"
    if minutes < 60 * 24:
        hours = minutes / 60.0
        return f"{hours:.1f}h" if hours < 10 else f"{hours:.0f}h"
    days = minutes / (60.0 * 24.0)
    return f"{days:.1f}d" if days < 10 else f"{days:.0f}d"


def wrap_text(text: str, max_chars: int, max_lines: int) -> list[str]:
    """Greedy word wrap with an ellipsis on overflow."""
    lines: list[str] = []
    cur = ""
    for word in text.split():
        cand = (cur + " " + word).strip()
        if len(cand) > max_chars and cur:
            lines.append(cur)
            cur = word
        else:
            cur = cand
    if cur:
        lines.append(cur)
    if not lines:
        return [""]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: max_chars - 1].rstrip() + "…"
    return lines


def lane_order(stages: list[dict]) -> list[str]:
    """Lanes ordered by first appearance, so the diagram reads top-left down."""
    seen: list[str] = []
    for s in stages:
        if s["owner"] not in seen:
            seen.append(s["owner"])
    return seen


def bottleneck_indices(normalized: dict, profile: str) -> tuple[int | None, set[int]]:
    """(primary constraint index, all flagged indices) from bottleneck_detector."""
    findings = detect(normalized, profile)
    flagged = {f.stage_index for f in findings if f.stage_index is not None}
    primary = None
    for f in findings:  # findings are pre-sorted by severity then impact
        if f.stage_index is not None:
            primary = f.stage_index
            break
    return primary, flagged


# --------------------------------------------------------------------------
# SVG
# --------------------------------------------------------------------------

def render_svg(normalized: dict, primary: int | None, flagged: set[int]) -> str:
    stages = normalized["stages"]
    lanes = lane_order(stages)
    lane_y = {name: i for i, name in enumerate(lanes)}

    lanes_h = len(lanes) * LANE_H
    width = LANE_LABEL_W + len(stages) * (BOX_W + GAP_X) + MARGIN
    height = lanes_h + RIBBON_H + 46

    def box_x(i: int) -> int:
        return LANE_LABEL_W + i * (BOX_W + GAP_X) + GAP_X // 2

    def box_y(stage: dict) -> int:
        return lane_y[stage["owner"]] * LANE_H + LANE_PAD

    out: list[str] = []
    out.append(
        f'<svg class="diagram" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" '
        f'aria-label="Swim-lane diagram of {html.escape(normalized["process_name"])}" '
        f'xmlns="http://www.w3.org/2000/svg">'
    )
    out.append(
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
        '<path d="M 0 0 L 10 5 L 0 10 z" class="arrowhead"/></marker></defs>'
    )

    # Lane bands + labels
    for name, idx in lane_y.items():
        y = idx * LANE_H
        band = "band-odd" if idx % 2 else "band-even"
        out.append(f'<rect class="{band}" x="0" y="{y}" width="{width}" height="{LANE_H}"/>')
        out.append(f'<line class="lane-rule" x1="0" y1="{y}" x2="{width}" y2="{y}"/>')
        label_lines = wrap_text(name, 22, 2)
        start_y = y + LANE_H / 2 - (len(label_lines) - 1) * 9
        for li, text in enumerate(label_lines):
            out.append(
                f'<text class="lane-label" x="16" y="{start_y + li * 18:.0f}" '
                f'dominant-baseline="middle">{html.escape(text)}</text>'
            )
    out.append(f'<line class="lane-rule" x1="0" y1="{lanes_h}" x2="{width}" y2="{lanes_h}"/>')
    out.append(
        f'<line class="lane-divider" x1="{LANE_LABEL_W}" y1="0" '
        f'x2="{LANE_LABEL_W}" y2="{lanes_h}"/>'
    )

    # Connectors first, so stage boxes paint over them.
    for i in range(len(stages) - 1):
        a, b = stages[i], stages[i + 1]
        ax = box_x(i) + BOX_W
        ay = box_y(a) + BOX_H / 2
        bx = box_x(i + 1)
        by = box_y(b) + BOX_H / 2
        mid = (ax + bx) / 2
        cls = "link link-handoff" if a["owner"] != b["owner"] else "link"
        if ay == by:
            pts = f"{ax},{ay} {bx},{by}"
        else:
            pts = f"{ax},{ay} {mid},{ay} {mid},{by} {bx},{by}"
        out.append(f'<polyline class="{cls}" points="{pts}" marker-end="url(#arrow)"/>')

    # Stage boxes
    for i, s in enumerate(stages):
        x, y = box_x(i), box_y(s)
        stype = s["type"]
        classes = f"stage stage-{stype.replace('-', '')}"
        if i == primary:
            classes += " stage-primary"
        elif i in flagged:
            classes += " stage-flagged"
        out.append(f'<g class="{classes}">')
        out.append(f'<rect class="stage-box" x="{x}" y="{y}" rx="9" width="{BOX_W}" height="{BOX_H}"/>')
        out.append(
            f'<text class="stage-num" x="{x + 12}" y="{y + 19}">'
            f'{TYPE_GLYPH.get(stype, "")} {i + 1}</text>'
        )
        out.append(
            f'<text class="stage-dur" x="{x + BOX_W - 12}" y="{y + 19}" text-anchor="end">'
            f'{fmt_duration(s["duration_minutes_p50"])}</text>'
        )
        for li, text in enumerate(wrap_text(s["name"], 26, 3)):
            out.append(
                f'<text class="stage-name" x="{x + 12}" y="{y + 38 + li * 14}">'
                f'{html.escape(text)}</text>'
            )
        out.append("</g>")
        if i == primary:
            out.append(
                f'<text class="constraint-tag" x="{x + BOX_W / 2}" y="{y - 5}" '
                f'text-anchor="middle">CONSTRAINT</text>'
            )

    # Value-stream time ribbon
    total = sum(s["duration_minutes_p50"] for s in stages) or 1.0
    ribbon_y = lanes_h + 34
    avail = width - LANE_LABEL_W - MARGIN
    out.append(
        f'<text class="ribbon-title" x="16" y="{ribbon_y + 6}">'
        f'Elapsed time (P50)</text>'
    )
    out.append(
        f'<text class="ribbon-sub" x="16" y="{ribbon_y + 24}">'
        f'segment width = share of total</text>'
    )
    cursor = float(LANE_LABEL_W)
    for i, s in enumerate(stages):
        seg = s["duration_minutes_p50"] / total * avail
        stype = s["type"]
        cls = f"ribbon ribbon-{stype.replace('-', '')}"
        if i == primary:
            cls += " ribbon-primary"
        out.append(
            f'<rect class="{cls}" x="{cursor:.1f}" y="{ribbon_y - 12}" '
            f'width="{max(seg, 0.8):.1f}" height="34"/>'
        )
        if seg > 46:
            out.append(
                f'<text class="ribbon-label" x="{cursor + seg / 2:.1f}" '
                f'y="{ribbon_y + 30}" text-anchor="middle">'
                f'{fmt_duration(s["duration_minutes_p50"])}</text>'
            )
        cursor += seg
    out.append("</svg>")
    return "\n".join(out)


CSS = """
:root {
  --bg: #ffffff; --surface: #f6f7f9; --band: #fafbfc; --band-alt: #f1f3f6;
  --text: #14181f; --muted: #5b6572; --rule: #dfe3e9; --divider: #b9c0ca;
  --va-fill: #e3f2ea; --va-stroke: #2f7d55; --va-solid: #35895e;
  --wait-fill: #fdf1dc; --wait-stroke: #a9752a; --wait-solid: #c98f34;
  --rework-fill: #fbe4e4; --rework-stroke: #a63d3d; --rework-solid: #c14f4f;
  --primary: #b3261e; --link: #97a1ae; --focus: #4338ca;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #12151a; --surface: #191d24; --band: #171b21; --band-alt: #1d222a;
    --text: #e8ecf1; --muted: #9aa5b3; --rule: #2a313b; --divider: #3d4652;
    --va-fill: #17322a; --va-stroke: #5fbb8c; --va-solid: #46a173;
    --wait-fill: #33280f; --wait-stroke: #d9a955; --wait-solid: #b98c39;
    --rework-fill: #341a1c; --rework-stroke: #e07b7b; --rework-solid: #b95757;
    --primary: #ff6b5e; --link: #5c6774;
  }
}
:root[data-theme="dark"] {
  --bg: #12151a; --surface: #191d24; --band: #171b21; --band-alt: #1d222a;
  --text: #e8ecf1; --muted: #9aa5b3; --rule: #2a313b; --divider: #3d4652;
  --va-fill: #17322a; --va-stroke: #5fbb8c; --va-solid: #46a173;
  --wait-fill: #33280f; --wait-stroke: #d9a955; --wait-solid: #b98c39;
  --rework-fill: #341a1c; --rework-stroke: #e07b7b; --rework-solid: #b95757;
  --primary: #ff6b5e; --link: #5c6774; --focus: #a5b4fc;
}
:root[data-theme="light"] {
  --bg: #ffffff; --surface: #f6f7f9; --band: #fafbfc; --band-alt: #f1f3f6;
  --text: #14181f; --muted: #5b6572; --rule: #dfe3e9; --divider: #b9c0ca;
  --va-fill: #e3f2ea; --va-stroke: #2f7d55; --va-solid: #35895e;
  --wait-fill: #fdf1dc; --wait-stroke: #a9752a; --wait-solid: #c98f34;
  --rework-fill: #fbe4e4; --rework-stroke: #a63d3d; --rework-solid: #c14f4f;
  --primary: #b3261e; --link: #97a1ae; --focus: #4338ca;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--text);
  font-family: ui-sans-serif, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  line-height: 1.5;
}
.wrap { max-width: 1180px; margin: 0 auto; padding: 32px 20px 64px; }
h1, h2, h3 { text-wrap: balance; }
h1 { font-size: 1.65rem; margin: 0 0 4px; letter-spacing: -0.01em; }
.sub { color: var(--muted); font-size: 0.92rem; margin: 0 0 24px; }
.stats { display: flex; flex-wrap: wrap; gap: 10px; margin: 0 0 22px; padding: 0; list-style: none; }
.stat {
  background: var(--surface); border: 1px solid var(--rule); border-radius: 10px;
  padding: 10px 14px; min-width: 116px;
}
.stat .k { display: block; font-size: 0.72rem; text-transform: uppercase;
  letter-spacing: 0.05em; color: var(--muted); }
.stat .v { display: block; font-size: 1.18rem; font-weight: 650; margin-top: 2px;
  font-variant-numeric: tabular-nums; }
.verdict-HEALTHY .v { color: var(--va-solid); }
.verdict-TYPICAL .v { color: var(--wait-solid); }
.verdict-WASTEHEAVY .v { color: var(--primary); }
.scroller {
  overflow-x: auto; border: 1px solid var(--rule); border-radius: 12px;
  background: var(--bg);
}
.scroller:focus-visible { outline: 2px solid var(--focus); outline-offset: 3px; }
svg.diagram { display: block; min-width: 100%; }
.band-even { fill: var(--band); }
.band-odd { fill: var(--band-alt); }
.lane-rule { stroke: var(--rule); stroke-width: 1; }
.lane-divider { stroke: var(--divider); stroke-width: 1.5; }
.lane-label { font-size: 13px; font-weight: 640; fill: var(--text); }
.link { fill: none; stroke: var(--link); stroke-width: 1.6; }
.link-handoff { stroke-dasharray: 5 4; }
.arrowhead { fill: var(--link); }
.stage-box { stroke-width: 1.5; }
.stagevalueadd .stage-box { fill: var(--va-fill); stroke: var(--va-stroke); }
.stagewait .stage-box { fill: var(--wait-fill); stroke: var(--wait-stroke); }
.stagerework .stage-box { fill: var(--rework-fill); stroke: var(--rework-stroke); }
/* The constraint marker uses its own hue, NOT the rework red: stage type and
   "this is the constraint" are two different facts and must not share a color. */
.stage-primary .stage-box { stroke: var(--focus); stroke-width: 3.5; }
.stage-flagged .stage-box { stroke-width: 2.5; stroke-dasharray: 6 3; }
.stage-num { font-size: 11px; font-weight: 700; fill: var(--muted); }
.stage-dur { font-size: 11px; font-weight: 700; fill: var(--muted);
  font-variant-numeric: tabular-nums; }
.stage-name { font-size: 12px; fill: var(--text); }
.constraint-tag { font-size: 9.5px; font-weight: 800; fill: var(--focus);
  letter-spacing: 0.09em; }
.ribbon-title { font-size: 12.5px; font-weight: 660; fill: var(--text); }
.ribbon-sub { font-size: 10.5px; fill: var(--muted); }
.ribbonvalueadd { fill: var(--va-solid); }
.ribbonwait { fill: var(--wait-solid); }
.ribbonrework { fill: var(--rework-solid); }
.ribbon-primary { stroke: var(--focus); stroke-width: 2.5; }
.ribbon-label { font-size: 10px; fill: var(--muted);
  font-variant-numeric: tabular-nums; }
.legend { display: flex; flex-wrap: wrap; gap: 18px; margin: 16px 0 0;
  padding: 0; list-style: none; font-size: 0.85rem; color: var(--muted); }
.legend li { display: flex; align-items: center; gap: 7px; }
.swatch { width: 14px; height: 14px; border-radius: 4px; border: 1.5px solid; }
.sw-va { background: var(--va-fill); border-color: var(--va-stroke); }
.sw-wait { background: var(--wait-fill); border-color: var(--wait-stroke); }
.sw-rework { background: var(--rework-fill); border-color: var(--rework-stroke); }
.sw-primary { background: transparent; border-color: var(--focus); border-width: 3px; }
h2 { font-size: 1.12rem; margin: 34px 0 12px; }
.finding {
  border: 1px solid var(--rule); border-left: 4px solid var(--rule);
  border-radius: 9px; padding: 13px 16px; margin-bottom: 11px; background: var(--surface);
}
.finding.CRITICAL { border-left-color: var(--primary); }
.finding.HIGH { border-left-color: var(--wait-solid); }
.finding.MEDIUM { border-left-color: var(--link); }
.finding h3 { margin: 0 0 6px; font-size: 0.97rem; }
.tag { display: inline-block; font-size: 0.68rem; font-weight: 750;
  letter-spacing: 0.06em; padding: 2px 7px; border-radius: 5px;
  border: 1px solid currentColor; margin-right: 8px; vertical-align: 1px; }
.finding.CRITICAL .tag { color: var(--primary); }
.finding.HIGH .tag { color: var(--wait-solid); }
.finding.MEDIUM .tag { color: var(--muted); }
.finding p { margin: 5px 0; font-size: 0.89rem; }
.finding .lab { color: var(--muted); font-weight: 640; }
.note { font-size: 0.85rem; color: var(--muted); border-top: 1px solid var(--rule);
  margin-top: 30px; padding-top: 14px; }
@media print {
  body { background: #fff; }
  .scroller { border: none; overflow: visible; }
  .wrap { max-width: none; padding: 0; }
}
"""


def render_html(
    normalized: dict, profile: str, title: str | None, fragment: bool = False
) -> str:
    stages = normalized["stages"]
    name = title or normalized["process_name"]
    report = analyze(normalized, profile)
    findings = detect(normalized, profile)
    primary, flagged = bottleneck_indices(normalized, profile)
    svg = render_svg(normalized, primary, flagged)

    verdict_cls = "verdict-" + report.verdict.replace("-", "")
    stats = [
        ("Stages", str(report.stage_count)),
        ("Lanes", str(len(lane_order(stages)))),
        ("Total P50", fmt_duration(report.total_p50_minutes)),
        ("Total P90", fmt_duration(report.total_p90_minutes)),
        ("Value-add", f"{report.value_add_ratio * 100:.0f}%"),
        ("Wait", f"{report.wait_ratio * 100:.0f}%"),
        ("Rework", f"{report.rework_ratio * 100:.0f}%"),
    ]

    p: list[str] = []
    p.append('<div class="wrap">')
    p.append(f"<h1>{html.escape(name)}</h1>")
    p.append(
        f'<p class="sub">Swim-lane process map &middot; profile '
        f'<code>{html.escape(profile)}</code> &middot; '
        f'{len(stages)} stages across {len(lane_order(stages))} lanes</p>'
    )
    p.append('<ul class="stats">')
    for k, v in stats:
        p.append(f'<li class="stat"><span class="k">{k}</span><span class="v">{v}</span></li>')
    p.append(
        f'<li class="stat {verdict_cls}"><span class="k">Verdict</span>'
        f'<span class="v">{report.verdict}</span></li>'
    )
    p.append("</ul>")
    p.append(
        f'<div class="scroller" tabindex="0" role="group" '
        f'aria-label="Swim-lane diagram, scrollable horizontally">{svg}</div>'
    )
    p.append('<ul class="legend">')
    p.append('<li><span class="swatch sw-va"></span>Value-add</li>')
    p.append('<li><span class="swatch sw-wait"></span>Wait / queue</li>')
    p.append('<li><span class="swatch sw-rework"></span>Rework</li>')
    p.append('<li><span class="swatch sw-primary"></span>Primary constraint</li>')
    p.append('<li>Dashed arrow = handoff between lanes</li>')
    p.append("</ul>")

    p.append(f"<h2>Bottleneck findings ({len(findings)})</h2>")
    if not findings:
        p.append("<p>No bottlenecks detected at this profile's thresholds.</p>")
    for f in findings:
        p.append(f'<div class="finding {html.escape(f.severity)}">')
        p.append(
            f'<h3><span class="tag">{html.escape(f.severity)}</span>'
            f'{html.escape(f.title)}</h3>'
        )
        p.append(f'<p>{html.escape(f.detail)}</p>')
        p.append(f'<p><span class="lab">Hypothesis:</span> {html.escape(f.hypothesis)}</p>')
        p.append(f'<p><span class="lab">Action:</span> {html.escape(f.action)}</p>')
        p.append("</div>")

    if report.notes:
        p.append("<h2>Notes</h2>")
        for n in report.notes:
            p.append(f"<p>{html.escape(n)}</p>")

    p.append(
        '<p class="note">Generated by process-mapper. Stage durations are only as '
        'good as their source: replace estimates with measured data before acting. '
        'Per Goldratt, subordinate improvements to the constraint &mdash; speeding up '
        'a non-constraint stage adds inventory in front of the constraint, not throughput.</p>'
    )
    p.append("</div>")
    body = "\n".join(p)

    if fragment:
        # Body-level content only: for embedding in a host page that supplies
        # its own <!doctype>/<head>/<body> (Claude Artifacts, Confluence, a
        # static-site template).
        return f"<style>{CSS}</style>\n{body}\n"

    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(name)} — Swim-lane Map</title>\n"
        f"<style>{CSS}</style>\n</head>\n<body>\n{body}\n</body>\n</html>\n"
    )


# --------------------------------------------------------------------------
# Mermaid
# --------------------------------------------------------------------------

def render_mermaid(normalized: dict, profile: str, title: str | None) -> str:
    stages = normalized["stages"]
    name = title or normalized["process_name"]
    primary, _ = bottleneck_indices(normalized, profile)
    lanes = lane_order(stages)

    def node_id(i: int) -> str:
        return f"s{i}"

    def label(i: int, s: dict) -> str:
        # Mermaid label text: quotes break the node, so strip them.
        text = s["name"].replace('"', "'")
        return f'{i + 1}. {text}<br/><small>{fmt_duration(s["duration_minutes_p50"])}</small>'

    out: list[str] = []
    out.append(f"%% {name} — swim-lane map (profile: {profile})")
    out.append("%% Generated by process-mapper / swimlane_renderer.py")
    out.append("flowchart LR")
    for lane in lanes:
        safe_lane = lane.replace('"', "'")
        out.append(f'  subgraph {_lane_id(lane)}["{safe_lane}"]')
        out.append("    direction LR")
        for i, s in enumerate(stages):
            if s["owner"] == lane:
                out.append(f'    {node_id(i)}["{label(i, s)}"]')
        out.append("  end")
    out.append("")
    for i in range(len(stages) - 1):
        arrow = "-.->" if stages[i]["owner"] != stages[i + 1]["owner"] else "-->"
        out.append(f"  {node_id(i)} {arrow} {node_id(i + 1)}")
    out.append("")
    out.append("  classDef va fill:#e3f2ea,stroke:#2f7d55,color:#14181f;")
    out.append("  classDef wait fill:#fdf1dc,stroke:#a9752a,color:#14181f;")
    out.append("  classDef rework fill:#fbe4e4,stroke:#a63d3d,color:#14181f;")
    # Constraint hue is deliberately distinct from the three stage-type colors:
    # "this is the constraint" is a different fact from "this stage is rework".
    out.append("  classDef constraint stroke:#4338ca,stroke-width:4px;")
    cls_map = {"value-add": "va", "wait": "wait", "rework": "rework"}
    for key, cls in cls_map.items():
        members = [node_id(i) for i, s in enumerate(stages) if s["type"] == key]
        if members:
            out.append(f"  class {','.join(members)} {cls};")
    if primary is not None:
        out.append(f"  class {node_id(primary)} constraint;")
    return "\n".join(out)


def _lane_id(lane: str) -> str:
    keep = [c if c.isalnum() else "_" for c in lane]
    return "lane_" + "".join(keep)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render a business process as a visual swim-lane diagram."
    )
    parser.add_argument("--input", type=Path, help="Path to process JSON file.")
    parser.add_argument(
        "--output",
        choices=["html", "mermaid"],
        default="html",
        help="Output format (default: html).",
    )
    parser.add_argument(
        "--profile",
        choices=sorted(BOTTLENECK_PROFILES.keys()),
        default="saas",
        help="Industry profile used to pick the highlighted constraint "
             "(default: saas). Matches bottleneck_detector.py.",
    )
    parser.add_argument("--title", help="Override the process title in the output.")
    parser.add_argument(
        "--fragment",
        action="store_true",
        help="HTML only: emit <style> + body content without the document "
             "wrapper, for embedding in a host page.",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        help="Write output to this file instead of stdout.",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Use the built-in sample process.",
    )
    args = parser.parse_args()

    normalized = resolve(args, parser)

    if args.output == "mermaid":
        if args.fragment:
            parser.error("--fragment applies to --output html only")
        out = render_mermaid(normalized, args.profile, args.title)
    else:
        out = render_html(normalized, args.profile, args.title, args.fragment)

    if args.dest:
        args.dest.write_text(out, encoding="utf-8")
        print(f"wrote {args.dest}", file=sys.stderr)
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
