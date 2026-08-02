#!/usr/bin/env python3
"""process_documenter.py

Read a JSON description of a business process (one entry per stage) and emit:
  - a text-based BPMN-style swim-lane diagram in Markdown, OR
  - a normalized JSON artifact for downstream tools.

Stdlib only. Use `--sample` to run against a built-in 6-stage
procurement-intake example.

The input schema, its validation rules, and the shared exit-code convention
live in `process_model.py`. Invalid input exits 3.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from process_model import resolve  # noqa: E402


def render_markdown(normalized: dict) -> str:
    """Render a text-based BPMN-style swim-lane diagram in Markdown."""
    name = normalized["process_name"]
    stages = normalized["stages"]
    lines: list[str] = []

    lines.append(f"# Process Map: {name}")
    lines.append("")
    lines.append(f"**Stages:** {len(stages)}  ")
    lines.append(
        f"**Total P50:** {sum(s['duration_minutes_p50'] for s in stages):.1f} min  "
    )
    lines.append(
        f"**Total P90:** {sum(s['duration_minutes_p90'] for s in stages):.1f} min"
    )
    lines.append("")

    # Group by owner -> swim lane
    lanes: dict[str, list[tuple[int, dict]]] = {}
    for idx, s in enumerate(stages):
        lanes.setdefault(s["owner"], []).append((idx, s))

    lines.append("## Swim Lanes")
    lines.append("")
    type_glyph = {"value-add": "[V]", "wait": "[W]", "rework": "[R]"}
    lane_width = max(20, max((len(o) for o in lanes), default=20) + 4)
    sep = "+" + "-" * (lane_width + 2) + "+" + "-" * 72 + "+"

    lines.append("```")
    lines.append(sep)
    lines.append(
        "| " + "OWNER".ljust(lane_width) + " | " + "STAGES (in process order)".ljust(70) + " |"
    )
    lines.append(sep)
    for owner, owned in lanes.items():
        owner_cell = owner.ljust(lane_width)
        cells = []
        for idx, s in owned:
            glyph = type_glyph.get(s["type"], "[?]")
            cells.append(
                f"#{idx+1} {glyph} {s['name'][:32]} "
                f"(p50={s['duration_minutes_p50']:.0f}m)"
            )
        row_text = "  ->  ".join(cells)
        # Wrap row_text to 70 chars
        wrapped = []
        cur = ""
        for token in row_text.split(" "):
            if len(cur) + len(token) + 1 > 70:
                wrapped.append(cur)
                cur = token
            else:
                cur = (cur + " " + token).strip()
        if cur:
            wrapped.append(cur)
        for i, line in enumerate(wrapped):
            left = owner_cell if i == 0 else " " * lane_width
            lines.append(f"| {left} | {line.ljust(70)} |")
        lines.append(sep)
    lines.append("```")
    lines.append("")
    lines.append("Legend: `[V]` value-add  `[W]` wait  `[R]` rework")
    lines.append("")

    lines.append("## Linear sequence")
    lines.append("")
    lines.append("| # | Stage | Owner | Type | P50 (min) | P90 (min) |")
    lines.append("|---|-------|-------|------|-----------|-----------|")
    for idx, s in enumerate(stages):
        lines.append(
            f"| {idx+1} | {s['name']} | {s['owner']} | {s['type']} | "
            f"{s['duration_minutes_p50']:.1f} | {s['duration_minutes_p90']:.1f} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Document a business process as a BPMN-style swim-lane diagram."
    )
    parser.add_argument("--input", type=Path, help="Path to process JSON file.")
    parser.add_argument(
        "--output",
        "--format",
        dest="output",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown). --format is a deprecated alias.",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        help="Write output to this file instead of stdout.",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Run against the built-in 6-stage procurement-intake sample.",
    )
    args = parser.parse_args()

    normalized = resolve(args, parser)

    if args.output == "json":
        out = json.dumps(normalized, indent=2)
    else:
        out = render_markdown(normalized)

    if args.dest:
        args.dest.write_text(out, encoding="utf-8")
        print(f"wrote {args.dest}", file=sys.stderr)
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
