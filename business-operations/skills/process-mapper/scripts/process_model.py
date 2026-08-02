#!/usr/bin/env python3
"""process_model.py

Shared process-model primitives for the process-mapper tools.

This module is the single source of truth for:
  - the input schema and its validation rules,
  - the normalized dict every tool consumes,
  - the built-in sample process,
  - the shared exit-code convention.

It is a library, not a CLI. It exists because the four tools previously each
re-parsed the input independently: only `process_documenter.py` validated the
stage `type`, so a typo such as "value_add" silently produced an empty
value-add set, which flipped the cycle-time verdict and suppressed every
bottleneck finding with no warning at all.

Stdlib only.

Input schema (JSON):
{
  "process_name": "Procurement Intake",
  "wip": 12,                       # optional, integer; used by cycle_time_analyzer
  "stages": [
    {
      "name": "Requestor submits PO request",
      "owner": "Requestor",
      "type": "value-add",         # one of: value-add | wait | rework
      "duration_minutes_p50": 15,
      "duration_minutes_p90": 30
    },
    ...
  ]
}
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path


VALID_TYPES = {"value-add", "wait", "rework"}

# Exit-code convention, shared by every process-mapper CLI.
#   0 = success
#   2 = argparse usage error (argparse default)
#   3 = input rejected by validation
EXIT_INVALID_INPUT = 3


class StageType(str, Enum):
    VALUE_ADD = "value-add"
    WAIT = "wait"
    REWORK = "rework"


@dataclass
class Stage:
    name: str
    owner: str
    type: str
    duration_minutes_p50: float
    duration_minutes_p90: float

    def validate(self, idx: int) -> list[str]:
        errs: list[str] = []
        if not self.name:
            errs.append(f"stage[{idx}]: missing 'name'")
        if not self.owner:
            errs.append(f"stage[{idx}]: missing 'owner'")
        if self.type not in VALID_TYPES:
            errs.append(
                f"stage[{idx}] ('{self.name}'): invalid type '{self.type}' "
                f"(expected one of {sorted(VALID_TYPES)})"
            )
        if self.duration_minutes_p50 < 0:
            errs.append(f"stage[{idx}] ('{self.name}'): p50 must be >= 0")
        if self.duration_minutes_p90 < self.duration_minutes_p50:
            errs.append(
                f"stage[{idx}] ('{self.name}'): p90 ({self.duration_minutes_p90}) "
                f"< p50 ({self.duration_minutes_p50})"
            )
        return errs


def load_process(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize(raw: dict) -> dict:
    """Validate + return a normalized dict. Raises ValueError on bad input.

    Every stage error is collected before raising, so a user fixing a hand-typed
    process file sees all the problems at once rather than one per run.
    """
    if not isinstance(raw, dict):
        raise ValueError("input must be a JSON object")
    if "stages" not in raw or not isinstance(raw["stages"], list):
        raise ValueError("input must include a non-empty 'stages' list")
    if not raw["stages"]:
        raise ValueError("input must include a non-empty 'stages' list")

    stages: list[Stage] = []
    errors: list[str] = []
    for idx, s in enumerate(raw["stages"]):
        if not isinstance(s, dict):
            errors.append(f"stage[{idx}]: must be a JSON object")
            continue
        try:
            stage = Stage(
                name=s.get("name", ""),
                owner=s.get("owner", ""),
                type=s.get("type", ""),
                duration_minutes_p50=float(s.get("duration_minutes_p50", 0)),
                duration_minutes_p90=float(s.get("duration_minutes_p90", 0)),
            )
        except (TypeError, ValueError) as e:
            errors.append(f"stage[{idx}]: parse error: {e}")
            continue
        errors.extend(stage.validate(idx))
        stages.append(stage)

    try:
        wip = int(raw.get("wip", 0) or 0)
    except (TypeError, ValueError):
        errors.append(f"'wip' must be an integer, got {raw.get('wip')!r}")
        wip = 0

    if errors:
        raise ValueError("invalid input:\n  - " + "\n  - ".join(errors))

    return {
        "process_name": raw.get("process_name", "Untitled Process"),
        "wip": wip,
        "stages": [asdict(s) for s in stages],
    }


def load_raw(args: argparse.Namespace, parser: argparse.ArgumentParser) -> dict:
    """Resolve --sample / --input into a raw dict, with clean errors."""
    if getattr(args, "sample", False):
        return sample_process()
    if not args.input:
        parser.error("--input is required unless --sample is given")
    if not args.input.exists():
        parser.error(f"input file not found: {args.input}")
    try:
        return load_process(args.input)
    except json.JSONDecodeError as e:
        print(f"ERROR: {args.input} is not valid JSON: {e}", file=sys.stderr)
        raise SystemExit(EXIT_INVALID_INPUT)
    except OSError as e:
        print(f"ERROR: could not read {args.input}: {e}", file=sys.stderr)
        raise SystemExit(EXIT_INVALID_INPUT)


def normalize_or_exit(raw: dict) -> dict:
    """normalize() with the shared refusal behavior: print + exit 3."""
    try:
        return normalize(raw)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(EXIT_INVALID_INPUT)


def resolve(args: argparse.Namespace, parser: argparse.ArgumentParser) -> dict:
    """Load and validate in one step. The standard entry point for every tool."""
    return normalize_or_exit(load_raw(args, parser))


def sample_process() -> dict:
    """The built-in 6-stage procurement-intake example.

    Defined once here so every tool reports identical stage names; the three
    tools previously carried three drifting copies of this data.
    """
    return {
        "process_name": "Procurement Intake (Sample)",
        "wip": 12,
        "stages": [
            {
                "name": "Requestor submits PO request",
                "owner": "Requestor",
                "type": "value-add",
                "duration_minutes_p50": 15,
                "duration_minutes_p90": 30,
            },
            {
                "name": "Wait for manager review queue",
                "owner": "Manager",
                "type": "wait",
                "duration_minutes_p50": 480,
                "duration_minutes_p90": 1440,
            },
            {
                "name": "Manager approves request",
                "owner": "Manager",
                "type": "value-add",
                "duration_minutes_p50": 10,
                "duration_minutes_p90": 25,
            },
            {
                "name": "Wait for finance review queue",
                "owner": "Finance",
                "type": "wait",
                "duration_minutes_p50": 720,
                "duration_minutes_p90": 2880,
            },
            {
                "name": "Finance validates budget code",
                "owner": "Finance",
                "type": "value-add",
                "duration_minutes_p50": 20,
                "duration_minutes_p90": 60,
            },
            {
                "name": "Rework: missing vendor W-9",
                "owner": "Requestor",
                "type": "rework",
                "duration_minutes_p50": 120,
                "duration_minutes_p90": 360,
            },
        ],
    }
