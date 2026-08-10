"""Preview truth gate — environment ceilings and production readback evidence.

A deployment target limits the strongest claim category that may be considered.
`PRODUCTION_VERIFIED` additionally requires exact source readback plus explicit,
boolean semantic invariants. Lower-strength target ceilings are not themselves
proof that testing or deployment occurred.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
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


_RANK = MappingProxyType(
    {
        ClaimStrength.MARKETING: 0,
        ClaimStrength.TESTED: 1,
        ClaimStrength.DEPLOYED: 2,
        ClaimStrength.PRODUCTION_VERIFIED: 3,
    }
)
_MAX = MappingProxyType(
    {
        DeployTarget.PREVIEW: ClaimStrength.TESTED,
        DeployTarget.STAGING: ClaimStrength.DEPLOYED,
        DeployTarget.PRODUCTION: ClaimStrength.PRODUCTION_VERIFIED,
    }
)
_CHECK_NAME_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
_SOURCE_REF_RE = re.compile(r"^[A-Za-z0-9_.:/-]+$")


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class DeploymentEvidence:
    expected_source_sha: str
    observed_source_sha: str
    semantic_checks: Mapping[str, bool]

    def __post_init__(self) -> None:
        for field_name, value in (
            ("expected_source_sha", self.expected_source_sha),
            ("observed_source_sha", self.observed_source_sha),
        ):
            if (
                not isinstance(value, str)
                or not value
                or not _SOURCE_REF_RE.fullmatch(value)
            ):
                raise ValueError(f"{field_name} must be a non-empty machine-safe source ref")
        if not isinstance(self.semantic_checks, Mapping):
            raise ValueError("semantic_checks must be a mapping")

        normalized: dict[str, bool] = {}
        for name, passed in self.semantic_checks.items():
            if (
                not isinstance(name, str)
                or not name
                or not _CHECK_NAME_RE.fullmatch(name)
            ):
                raise ValueError("semantic check names must be non-empty machine-safe tokens")
            if not isinstance(passed, bool):
                raise ValueError("semantic check results must be boolean")
            normalized[name] = passed

        object.__setattr__(
            self,
            "semantic_checks",
            MappingProxyType(dict(sorted(normalized.items()))),
        )

    def normalized(self) -> dict[str, object]:
        return {
            "expected_source_sha": self.expected_source_sha,
            "observed_source_sha": self.observed_source_sha,
            "semantic_checks": dict(self.semantic_checks),
        }

    def fingerprint(self) -> str:
        return _fingerprint(self.normalized())


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    reason: str | None
    max_target_strength: ClaimStrength
    evidence_fingerprint: str | None
    fingerprint: str


def max_claim_for(target: DeployTarget) -> ClaimStrength:
    if not isinstance(target, DeployTarget):
        raise ValueError("target must be DeployTarget")
    return _MAX[target]


def evaluate_claim(
    target: DeployTarget,
    strength: ClaimStrength,
    evidence: DeploymentEvidence | None = None,
) -> GateDecision:
    """Evaluate a claim and produce a deterministic decision receipt.

    Environment ceilings prevent preview/staging evidence from authorizing a
    production-verified claim. `PRODUCTION_VERIFIED` additionally requires an
    exact source-ref readback and at least one named semantic invariant, with
    every invariant explicitly boolean-true.
    """
    if not isinstance(target, DeployTarget):
        raise ValueError("target must be DeployTarget")
    if not isinstance(strength, ClaimStrength):
        raise ValueError("strength must be ClaimStrength")
    if evidence is not None and not isinstance(evidence, DeploymentEvidence):
        raise ValueError("evidence must be DeploymentEvidence or None")

    mx = max_claim_for(target)
    reason: str | None = None

    if _RANK[strength] > _RANK[mx]:
        reason = f"TARGET_{target.value}_MAX_{mx.value}"
    elif strength is ClaimStrength.PRODUCTION_VERIFIED:
        if target is not DeployTarget.PRODUCTION:
            reason = "PRODUCTION_TARGET_REQUIRED"
        elif evidence is None:
            reason = "EVIDENCE_REQUIRED"
        elif evidence.expected_source_sha != evidence.observed_source_sha:
            reason = "SOURCE_SHA_MISMATCH"
        elif not evidence.semantic_checks:
            reason = "SEMANTIC_INVARIANT_REQUIRED"
        else:
            failed = [
                name for name, passed in evidence.semantic_checks.items() if not passed
            ]
            if failed:
                reason = "SEMANTIC_INVARIANT_FAILED:" + ",".join(failed)

    evidence_fp = evidence.fingerprint() if evidence else None
    payload = {
        "target": target.value,
        "strength": strength.value,
        "max_target_strength": mx.value,
        "allowed": reason is None,
        "reason": reason,
        "evidence_fingerprint": evidence_fp,
        "evidence": evidence.normalized() if evidence else None,
        "boundary": "target ceiling is not proof of lower-strength execution",
    }
    return GateDecision(
        allowed=reason is None,
        reason=reason,
        max_target_strength=mx,
        evidence_fingerprint=evidence_fp,
        fingerprint=_fingerprint(payload),
    )


def allow_claim(
    target: DeployTarget,
    strength: ClaimStrength,
    evidence: DeploymentEvidence | None = None,
) -> tuple[bool, str | None]:
    """Compatibility wrapper around :func:`evaluate_claim`."""
    decision = evaluate_claim(target, strength, evidence)
    return decision.allowed, decision.reason
