#!/usr/bin/env python3
"""Verify a deployment claim from extracted readback fields.

This is intentionally dependency-free for CI and release jobs. Callers must extract
readback values and pass them through --expected-sha, --observed-sha, and repeated
--check arguments. The gate fails closed on stale source identity, malformed input,
or semantic drift.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.preview_gate import ClaimStrength, DeployTarget, DeploymentEvidence, evaluate_claim


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=[t.value for t in DeployTarget], required=True)
    parser.add_argument("--strength", choices=[s.value for s in ClaimStrength], required=True)
    parser.add_argument("--expected-sha")
    parser.add_argument("--observed-sha")
    parser.add_argument(
        "--check",
        action="append",
        default=[],
        metavar="NAME=true|false",
        help="Semantic invariant result; repeat for multiple distinct checks.",
    )
    return parser.parse_args()


def parse_checks(values: list[str]) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    for item in values:
        if "=" not in item:
            raise ValueError(f"invalid check {item!r}: expected NAME=true|false")
        name, raw = item.split("=", 1)
        name = name.strip()
        if not name:
            raise ValueError("semantic check name must not be empty")
        if name in checks:
            raise ValueError(f"duplicate semantic check name: {name!r}")
        normalized = raw.strip().lower()
        if normalized not in {"true", "false"}:
            raise ValueError(f"invalid boolean for {name!r}: {raw!r}")
        checks[name] = normalized == "true"
    return checks


def main() -> int:
    args = parse_args()
    try:
        checks = parse_checks(args.check)
    except ValueError as exc:
        print(json.dumps({"allowed": False, "reason": "INVALID_INPUT", "detail": str(exc)}))
        return 2

    evidence = None
    if args.expected_sha is not None or args.observed_sha is not None or checks:
        evidence = DeploymentEvidence(
            args.expected_sha or "",
            args.observed_sha or "",
            checks,
        )

    decision = evaluate_claim(
        DeployTarget(args.target),
        ClaimStrength(args.strength),
        evidence,
    )
    print(
        json.dumps(
            {
                "allowed": decision.allowed,
                "reason": decision.reason,
                "fingerprint": decision.fingerprint,
            },
            sort_keys=True,
        )
    )
    return 0 if decision.allowed else 1


if __name__ == "__main__":
    raise SystemExit(main())
