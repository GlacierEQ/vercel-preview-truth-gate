#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from preview_gate import allow_claim, ClaimStrength, DeployTarget

def main() -> int:
    bad, reason = allow_claim(DeployTarget.PREVIEW, ClaimStrength.PRODUCTION_VERIFIED)
    good, _ = allow_claim(DeployTarget.PREVIEW, ClaimStrength.TESTED)
    out = {"preview_blocks_prod": not bad, "preview_allows_tested": good, "reason": reason,
           "ok": (not bad) and good}
    print(json.dumps(out, sort_keys=True))
    return 0 if out["ok"] else 1
if __name__ == "__main__":
    raise SystemExit(main())
