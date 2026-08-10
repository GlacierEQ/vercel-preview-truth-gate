from __future__ import annotations
import unittest
from src.preview_gate import (
    ClaimStrength,
    DeployTarget,
    DeploymentEvidence,
    allow_claim,
    evaluate_claim,
)


class PreviewTests(unittest.TestCase):
    def test_preview_blocks_prod_claim(self):
        ok, reason = allow_claim(DeployTarget.PREVIEW, ClaimStrength.PRODUCTION_VERIFIED)
        self.assertFalse(ok)
        self.assertEqual(reason, "TARGET_PREVIEW_MAX_TESTED")

    def test_staging_blocks_prod_claim(self):
        ok, reason = allow_claim(DeployTarget.STAGING, ClaimStrength.PRODUCTION_VERIFIED)
        self.assertFalse(ok)
        self.assertEqual(reason, "TARGET_STAGING_MAX_DEPLOYED")

    def test_production_verified_requires_evidence(self):
        ok, reason = allow_claim(DeployTarget.PRODUCTION, ClaimStrength.PRODUCTION_VERIFIED)
        self.assertFalse(ok)
        self.assertEqual(reason, "EVIDENCE_REQUIRED")

    def test_production_verified_rejects_sha_mismatch(self):
        evidence = DeploymentEvidence("expected", "observed", {"helix_consistent": True})
        ok, reason = allow_claim(
            DeployTarget.PRODUCTION,
            ClaimStrength.PRODUCTION_VERIFIED,
            evidence,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "SOURCE_SHA_MISMATCH")

    def test_production_verified_rejects_failed_semantics(self):
        evidence = DeploymentEvidence(
            "abc123",
            "abc123",
            {"homepage_resume_match": False, "machine_contract_match": True},
        )
        ok, reason = allow_claim(
            DeployTarget.PRODUCTION,
            ClaimStrength.PRODUCTION_VERIFIED,
            evidence,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "SEMANTIC_INVARIANT_FAILED:homepage_resume_match")

    def test_production_verified_accepts_bound_readback(self):
        evidence = DeploymentEvidence(
            "abc123",
            "abc123",
            {"homepage_resume_match": True, "machine_contract_match": True},
        )
        ok, reason = allow_claim(
            DeployTarget.PRODUCTION,
            ClaimStrength.PRODUCTION_VERIFIED,
            evidence,
        )
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_receipt_is_deterministic_and_evidence_bound(self):
        first = DeploymentEvidence("abc", "abc", {"b": True, "a": True})
        second = DeploymentEvidence("abc", "abc", {"a": True, "b": True})
        d1 = evaluate_claim(DeployTarget.PRODUCTION, ClaimStrength.PRODUCTION_VERIFIED, first)
        d2 = evaluate_claim(DeployTarget.PRODUCTION, ClaimStrength.PRODUCTION_VERIFIED, second)
        self.assertEqual(d1.fingerprint, d2.fingerprint)

        changed = DeploymentEvidence("abc", "abc", {"a": True, "b": False})
        d3 = evaluate_claim(DeployTarget.PRODUCTION, ClaimStrength.PRODUCTION_VERIFIED, changed)
        self.assertNotEqual(d1.fingerprint, d3.fingerprint)

    def test_lower_strength_production_claim_remains_allowed(self):
        ok, reason = allow_claim(DeployTarget.PRODUCTION, ClaimStrength.DEPLOYED)
        self.assertTrue(ok)
        self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main()
