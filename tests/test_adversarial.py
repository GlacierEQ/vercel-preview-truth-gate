from __future__ import annotations
import unittest
from src.preview_gate import allow_claim, ClaimStrength, DeployTarget

class Adv(unittest.TestCase):
    def test_preview_blocks_production_verified(self):
        ok, reason = allow_claim(DeployTarget.PREVIEW, ClaimStrength.PRODUCTION_VERIFIED)
        self.assertFalse(ok)
        self.assertIn("PREVIEW", reason or "")
    def test_staging_blocks_production_verified(self):
        ok, _ = allow_claim(DeployTarget.STAGING, ClaimStrength.PRODUCTION_VERIFIED)
        self.assertFalse(ok)
    def test_marketing_always_ok(self):
        ok, _ = allow_claim(DeployTarget.PREVIEW, ClaimStrength.MARKETING)
        self.assertTrue(ok)

