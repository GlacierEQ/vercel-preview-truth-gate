from __future__ import annotations
import unittest
from src.preview_gate import ClaimStrength, DeployTarget, allow_claim

class PreviewTests(unittest.TestCase):
    def test_preview_blocks_prod_claim(self):
        ok, reason = allow_claim(DeployTarget.PREVIEW, ClaimStrength.PRODUCTION_VERIFIED)
        self.assertFalse(ok)

    def test_production_allows(self):
        ok, _ = allow_claim(DeployTarget.PRODUCTION, ClaimStrength.PRODUCTION_VERIFIED)
        self.assertTrue(ok)

if __name__ == "__main__":
    unittest.main()
