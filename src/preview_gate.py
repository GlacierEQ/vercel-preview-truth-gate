"""Preview truth gate — deploy target bounds claim strength and binds strong claims to evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class DeployTarget(str, Enum):
    PREVIEW = "PREVIEW"
    STAGING = "STAGING"
    PRODUCTION = "PRODUCTION"


class ClaimStrength(str, Enum):
    MARKETING = "MARKETING"
    TESTED = "TESTED"
    DEPLOYED = "DEPLOYED"
    PRODUCTION_VERIFIED = "PRODUCTION_VERIFIED"


_RANK = {
    ClaimStrength.MARKETING: 0,
    ClaimStrength.TESTED: 1,
    ClaimStrength.DEPLOYED: 2,
    ClaimStrength.PRODUCTION_VERIFIED: 3,
}

_MAX = {
    DeployTarget.PREVIEW: ClaimStrength.TESTED,
    DeployTarget.STAGING: ClaimStrength.DEPLOYED,
    DeployTarget.PRODUCTION: ClaimStrength.PRODUCTION_VERIFIED,
}


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class DeploymentEvidence:
    expected_source_sha: str
    observed_source_sha: str
    semantic_checks: Mapping[str, bool]

    def normalized(self) -> dict[str, object]:
        return {
            "expected_source_sha": self.expected_source_sha,
            "observed_source_sha": self.observed_source_sha,
            "semantic_checks": dict(sorted(self.semantic_checks.items())),
        }


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    reason: str | None
    fingerprint: str


def max_claim_for(target: DeployTarget) -> ClaimStrength:
    return _MAX[target]


def evaluate_claim(
    target: DeployTarget,
    strength: ClaimStrength,
    evidence: DeploymentEvidence | None = None,
) -> GateDecision:
    """Evaluate a claim and produce a deterministic decision receipt.

    Target ceilings prevent obvious overclaiming. A PRODUCTION_VERIFIED claim also
    requires exact source-SHA readback and at least one named semantic invariant,
    with every declared invariant passing.
    """
    mx = max_claim_for(target)
    reason: str | None = None

    if _RANK[strength] > _RANK[mx]:
        reason = f"TARGET_{target.value}_MAX_{mx.value}"
    elif strength is ClaimStrength.PRODUCTION_VERIFIED:
        if target is not DeployTarget.PRODUCTION:
            reason = "PRODUCTION_TARGET_REQUIRED"
        elif evidence is None:
            reason = "EVIDENCE_REQUIRED"
        elif not evidence.expected_source_sha or not evidence.observed_source_sha:
            reason = "SOURCE_SHA_REQUIRED"
        elif evidence.expected_source_sha != evidence.observed_source_sha:
            reason = "SOURCE_SHA_MISMATCH"
        elif not evidence.semantic_checks:
            reason = "SEMANTIC_INVARIANT_REQUIRED"
        else:
            failed = sorted(name for name, ok in evidence.semantic_checks.items() if not ok)
            if failed:
                reason = "SEMANTIC_INVARIANT_FAILED:" + ",".join(failed)

    payload = {
        "target": target.value,
        "strength": strength.value,
        "allowed": reason is None,
        "reason": reason,
        "evidence": evidence.normalized() if evidence else None,
    }
    return GateDecision(reason is None, reason, _fingerprint(payload))


def allow_claim(
    target: DeployTarget,
    strength: ClaimStrength,
    evidence: DeploymentEvidence | None = None,
) -> tuple[bool, str | None]:
    """Compatibility wrapper around :func:`evaluate_claim`."""
    decision = evaluate_claim(target, strength, evidence)
    return decision.allowed, decision.reason
