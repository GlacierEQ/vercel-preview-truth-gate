#!/usr/bin/env python3
"""Deterministic offline demonstration of the live deployment verifier."""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.deployment_readback import ProbeSpec, VercelDeploymentVerifier
from src.preview_gate import DeployTarget


def main() -> int:
    sha = "a" * 40
    metadata = {
        "id": "dpl_demo",
        "url": "demo.vercel.app",
        "target": "production",
        "meta": {"githubCommitSha": sha},
    }

    def transport(method, url, headers, data, timeout):
        if "api.vercel.com" in url:
            return 200, {}, json.dumps(metadata).encode()
        if url.endswith("/api/health"):
            return 200, {}, b'{"ok":true,"service":"demo"}'
        return 200, {}, b"deployment demo ready"

    verifier = VercelDeploymentVerifier(
        "offline-demo-token", transport=transport, clock=lambda: 1234.0
    )
    receipt = verifier.verify(
        "demo.vercel.app",
        sha,
        [
            ProbeSpec("homepage", "/", 200, body_contains="ready"),
            ProbeSpec("health", "/api/health", 200, json_path="ok", json_equals=True),
        ],
        expected_target=DeployTarget.PRODUCTION,
    )
    print(json.dumps(receipt.as_dict(), indent=2, sort_keys=True))
    return 0 if receipt.decision.allowed else 1


if __name__ == "__main__":
    raise SystemExit(main())
