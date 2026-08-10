from __future__ import annotations
import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_deployment_claim.py"
spec = importlib.util.spec_from_file_location("verify_deployment_claim", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class VerifyDeploymentClaimTests(unittest.TestCase):
    def test_parse_checks(self):
        self.assertEqual(
            module.parse_checks(["homepage=true", "machine=false"]),
            {"homepage": True, "machine": False},
        )

    def test_parse_checks_rejects_bad_boolean(self):
        with self.assertRaises(ValueError):
            module.parse_checks(["homepage=maybe"])

    def test_parse_checks_rejects_missing_separator(self):
        with self.assertRaises(ValueError):
            module.parse_checks(["homepage"])

    def test_parse_checks_rejects_empty_name(self):
        with self.assertRaises(ValueError):
            module.parse_checks(["=true"])


if __name__ == "__main__":
    unittest.main()
