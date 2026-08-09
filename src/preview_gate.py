"""Preview truth gate — deploy target bounds claim strength."""
from __future__ import annotations

from enum import Enum


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


def max_claim_for(target: DeployTarget) -> ClaimStrength:
    return _MAX[target]


def allow_claim(target: DeployTarget, strength: ClaimStrength) -> tuple[bool, str | None]:
    mx = max_claim_for(target)
    if _RANK[strength] <= _RANK[mx]:
        return True, None
    return False, f"TARGET_{target.value}_MAX_{mx.value}"
