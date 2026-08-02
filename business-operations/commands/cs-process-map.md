---
description: Map an internal business process (BPMN-style swim lanes), measure cycle time, and detect bottlenecks where work spends most of its time waiting. Direct invocation of the process-mapper skill.
argument-hint: "<process description or path to process JSON>"
---

# /cs:process-map — BPMN-style process mapping + bottleneck detection

Run the `process-mapper` skill on this input:

**$ARGUMENTS**

## Four-tool workflow

1. **`process_documenter.py`** — Document the process as a BPMN-ish ASCII swim lane diagram. Input: stage list (name, owner, type{value-add/wait/rework}, P50 + P90 duration). Output: markdown diagram + normalized JSON.

2. **`cycle_time_analyzer.py`** — Compute total cycle time (P50, P90), value-add ratio (VA%), Little's Law throughput. Verdict on `saas`: VA% >= 25% HEALTHY / 10-25% TYPICAL / <10% WASTE-HEAVY. Bands shift per profile.

3. **`bottleneck_detector.py`** — Identify bottlenecks. Triggers: **value-add** stage P50 > 2× mean of value-add stages, OR wait-state % > 40% of total, OR rework % > 15%. Tunable via `--profile {saas,services,manufacturing,healthcare}`. R2/R3 name their own worst offender, so wait and rework stages are never double-reported by R1.

4. **`swimlane_renderer.py`** — Render the visual swim-lane: `--output html` (self-contained page: lanes, colour-coded stage types, highlighted constraint, value-stream time ribbon, embedded findings) or `--output mermaid` (renders in GitHub / Notion).

```bash
cd business-operations/skills/process-mapper

# Smoke-check the chain on the built-in sample
python3 scripts/process_documenter.py  --sample
python3 scripts/cycle_time_analyzer.py --sample --profile services
python3 scripts/bottleneck_detector.py --sample --profile services

# Real input (worked 18-stage procure-to-pay example ships in assets/)
python3 scripts/swimlane_renderer.py \
    --input assets/sample_p2p_process.json --profile services \
    --output html --dest p2p_swimlane.html
```

Shared CLI contract: `--input` / `--sample`, `--output` for format, `--dest` to write a file, `--profile` where thresholds apply. Invalid input exits **3** naming every offending stage; usage errors exit 2.

## Before running

Settle the **process boundary** first. If a stage inside it is owned by an external party (supplier, customer, regulator), run both scopes — end-to-end and internally-controllable — and label which scope each number came from. An end-to-end map often reports a constraint nobody in the room can act on.

## Output

- Process diagram (markdown + visual HTML/Mermaid swim-lane)
- Bottleneck list with severity + recommended action
- Cycle-time scorecard with VA% verdict
- Top 3 next actions

## Distinct from

- `engineering/slo-architect` — that's system reliability with SLO/SLI. This is **business process** reliability.
- `engineering/llm-wiki` — that's personal PKM. This is **company process documentation**.
- `c-level-advisor/coo-advisor` — that's strategic COO judgment. This is **tactical process mapping**.
