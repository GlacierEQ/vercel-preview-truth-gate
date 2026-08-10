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
        ok, reason = allow_claim(
            DeployTarget.PREVIEW, ClaimStrength.PRODUCTION_VERIFIED
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "TARGET_PREVIEW_MAX_TESTED")

    def test_staging_blocks_prod_claim(self):
        ok, reason = allow_claim(
            DeployTarget.STAGING, ClaimStrength.PRODUCTION_VERIFIED
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "TARGET_STAGING_MAX_DEPLOYED")

    def test_production_verified_requires_evidence(self):
        ok, reason = allow_claim(
            DeployTarget.PRODUCTION, ClaimStrength.PRODUCTION_VERIFIED
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "EVIDENCE_REQUIRED")

    def test_production_verified_rejects_sha_mismatch(self):
        evidence = DeploymentEvidence(
            "expected", "observed", {"helix_consistent": True}
        )
        ok, reason = allow_claim(
            DeployTarget.PRODUCTION,
            ClaimStrength.PRODUCTION_VERIFIED,
            evidence,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "SOURCE_SHA_MISMATCH")

    def test_production_verified_requires_named_semantic_invariant(self):
        evidence = DeploymentEvidence("abc123", "abc123", {})
        ok, reason = allow_claim(
            DeployTarget.PRODUCTION,
            ClaimStrength.PRODUCTION_VERIFIED,
            evidence,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "SEMANTIC_INVARIANT_REQUIRED")

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
        self.assertEqual(
            reason, "SEMANTIC_INVARIANT_FAILED:homepage_resume_match"
        )

    def test_production_verified_accepts_bound_readback(self):
        evidence = DeploymentEvidence(
            "abc123",
            "abc123",
            {"homepage_resume_match": True, "machine_contract_match": True},
        )
        decision = evaluate_claim(
            DeployTarget.PRODUCTION,
            ClaimStrength.PRODUCTION_VERIFIED,
            evidence,
        )
        self.assertTrue(decision.allowed)
        self.assertIsNone(decision.reason)
        self.assertEqual(decision.max_target_strength, ClaimStrength.PRODUCTION_VERIFIED)
        self.assertEqual(len(decision.evidence_fingerprint or ""), 64)

    def test_receipt_is_deterministic_and_evidence_bound(self):
        first = DeploymentEvidence("abc", "abc", {"b": True, "a": True})
        second = DeploymentEvidence("abc", "abc", {"a": True, "b": True})
        d1 = evaluate_claim(
            DeployTarget.PRODUCTION,
            ClaimStrength.PRODUCTION_VERIFIED,
            first,
        )
        d2 = evaluate_claim(
            DeployTarget.PRODUCTION,
            ClaimStrength.PRODUCTION_VERIFIED,
            second,
        )
        self.assertEqual(d1.fingerprint, d2.fingerprint)
        self.assertEqual(d1.evidence_fingerprint, d2.evidence_fingerprint)

        changed = DeploymentEvidence("abc", "abc", {"a": True, "b": False})
        d3 = evaluate_claim(
            DeployTarget.PRODUCTION,
            ClaimStrength.PRODUCTION_VERIFIED,
            changed,
        )
        self.assertNotEqual(d1.fingerprint, d3.fingerprint)
        self.assertNotEqual(d1.evidence_fingerprint, d3.evidence_fingerprint)

    def test_semantic_check_values_must_be_boolean(self):
        with self.assertRaisesRegex(ValueError, "must be boolean"):
            DeploymentEvidence(
                "abc", "abc", {"homepage_resume_match": "yes"}  # type: ignore[dict-item]
            )
        with self.assertRaisesRegex(ValueError, "must be boolean"):
            DeploymentEvidence(
                "abc", "abc", {"homepage_resume_match": 1}  # type: ignore[dict-item]
            )

    def test_semantic_check_names_must_be_machine_safe(self):
        with self.assertRaisesRegex(ValueError, "machine-safe"):
            DeploymentEvidence("abc", "abc", {"": True})
        with self.assertRaisesRegex(ValueError, "machine-safe"):
            DeploymentEvidence("abc", "abc", {"bad check": True})

    def test_source_refs_must_be_machine_safe(self):
        with self.assertRaisesRegex(ValueError, "source ref"):
            DeploymentEvidence("", "abc", {"check": True})
        with self.assertRaisesRegex(ValueError, "source ref"):
            DeploymentEvidence("abc", "bad ref", {"check": True})

    def test_evidence_mapping_is_frozen_at_construction(self):
        checks = {"a": True}
        evidence = DeploymentEvidence("abc", "abc", checks)
        checks["a"] = False
        decision = evaluate_claim(
            DeployTarget.PRODUCTION,
            ClaimStrength.PRODUCTION_VERIFIED,
            evidence,
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(dict(evidence.semantic_checks), {"a": True})

    def test_invalid_target_and_strength_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "target must be DeployTarget"):
            evaluate_claim("PRODUCTION", ClaimStrength.TESTED)  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValueError, "strength must be ClaimStrength"):
            evaluate_claim(DeployTarget.PRODUCTION, "TESTED")  # type: ignore[arg-type]

    def test_lower_strength_production_claim_is_ceiling_allowed_not_proven(self):
        decision = evaluate_claim(DeployTarget.PRODUCTION, ClaimStrength.DEPLOYED)
        self.assertTrue(decision.allowed)
        self.assertIsNone(decision.reason)
        self.assertIsNone(decision.evidence_fingerprint)
        self.assertEqual(decision.max_target_strength, ClaimStrength.PRODUCTION_VERIFIED)


if __name__ == "__main__":
    unittest.main()
