#!/usr/bin/env python3
"""Verify deployment truth from live Vercel readback or explicit upstream evidence."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.deployment_readback import ProbeSpec, VercelApiError, VercelDeploymentVerifier
from src.preview_gate import ClaimStrength, DeployTarget, DeploymentEvidence, evaluate_claim


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


def parse_probe(value: str) -> ProbeSpec:
    parts = value.split(",")
    if len(parts) < 3:
        raise argparse.ArgumentTypeError("probe must be NAME,PATH,STATUS[,contains=TEXT][,json=path:JSON_LITERAL]")
    name, path, raw_status, *options = parts
    try:
        status = int(raw_status)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("probe status must be an integer") from exc
    kwargs: dict[str, object] = {}
    for option in options:
        if option.startswith("contains="):
            kwargs["body_contains"] = option.removeprefix("contains=")
        elif option.startswith("json="):
            raw = option.removeprefix("json=")
            if ":" not in raw:
                raise argparse.ArgumentTypeError("json probe requires json=path:JSON_LITERAL")
            json_path, literal = raw.split(":", 1)
            kwargs["json_path"] = json_path
            try:
                kwargs["json_equals"] = json.loads(literal)
            except json.JSONDecodeError as exc:
                raise argparse.ArgumentTypeError("json expected value must be valid JSON") from exc
        else:
            raise argparse.ArgumentTypeError(f"unknown probe option: {option}")
    try:
        return ProbeSpec(name=name, path=path, expected_status=status, **kwargs)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def parse_headers(values: list[str]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for item in values:
        if "=" not in item:
            raise ValueError(f"invalid header {item!r}: expected NAME=VALUE")
        name, value = item.split("=", 1)
        name = name.strip()
        if not name:
            raise ValueError("header name must not be empty")
        if name in headers:
            raise ValueError(f"duplicate header name: {name!r}")
        headers[name] = value
    return headers


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=[t.value for t in DeployTarget])
    parser.add_argument("--strength", choices=[s.value for s in ClaimStrength], default=ClaimStrength.PRODUCTION_VERIFIED.value)
    parser.add_argument("--expected-sha", required=True)

    parser.add_argument("--deployment", help="Vercel deployment ID, hostname, or URL")
    parser.add_argument("--origin", help="Operational canonical origin when the deployment hostname is protected or noncanonical")
    parser.add_argument("--team-id", default=os.getenv("VERCEL_TEAM_ID"))
    parser.add_argument("--token", default=os.getenv("VERCEL_TOKEN"))
    parser.add_argument("--probe", action="append", type=parse_probe, default=[])
    parser.add_argument("--header", action="append", default=[], metavar="NAME=VALUE")
    parser.add_argument("--source-header", default=os.getenv("SOURCE_COMMIT_HEADER"), help="Runtime response header that carries the deployed source SHA")
    parser.add_argument("--source-path", default="/", help="Path used to read --source-header")

    parser.add_argument("--observed-sha")
    parser.add_argument("--check", action="append", default=[], metavar="NAME=true|false")
    return parser.parse_args()


def legacy_verify(args: argparse.Namespace) -> tuple[dict[str, object], int]:
    if not args.target:
        return {"allowed": False, "reason": "TARGET_REQUIRED"}, 2
    try:
        checks = parse_checks(args.check)
        evidence = DeploymentEvidence(args.expected_sha, args.observed_sha or "", checks)
    except ValueError as exc:
        return {"allowed": False, "reason": "INVALID_INPUT", "detail": str(exc)}, 2
    decision = evaluate_claim(DeployTarget(args.target), ClaimStrength(args.strength), evidence)
    result = {
        "mode": "explicit_evidence",
        "allowed": decision.allowed,
        "reason": decision.reason,
        "fingerprint": decision.fingerprint,
        "evidence_fingerprint": decision.evidence_fingerprint,
    }
    return result, 0 if decision.allowed else 1


def live_verify(args: argparse.Namespace) -> tuple[dict[str, object], int]:
    if not args.token:
        return {"allowed": False, "reason": "VERCEL_TOKEN_REQUIRED"}, 2
    if not args.probe:
        return {"allowed": False, "reason": "LIVE_PROBE_REQUIRED"}, 2
    try:
        headers = parse_headers(args.header)
        verifier = VercelDeploymentVerifier(args.token, team_id=args.team_id)
        receipt = verifier.verify(
            args.deployment,
            args.expected_sha,
            args.probe,
            requested_strength=ClaimStrength(args.strength),
            expected_target=DeployTarget(args.target) if args.target else None,
            deployment_headers=headers,
            runtime_origin=args.origin,
            source_header=args.source_header,
            source_path=args.source_path,
        )
    except (ValueError, VercelApiError) as exc:
        return {"allowed": False, "reason": type(exc).__name__, "detail": str(exc)}, 2
    result = receipt.as_dict()
    result["mode"] = "live_vercel_readback"
    return result, 0 if receipt.decision.allowed else 1


def main() -> int:
    args = parse_args()
    result, code = live_verify(args) if args.deployment else legacy_verify(args)
    print(json.dumps(result, sort_keys=True, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
