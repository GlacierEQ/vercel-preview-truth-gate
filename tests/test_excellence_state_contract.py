import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = json.loads((ROOT / "machine" / "excellence-state.json").read_text(encoding="utf-8"))
POSITION = json.loads((ROOT / "machine" / "canonical-position.json").read_text(encoding="utf-8"))


class ExcellenceStateContractTests(unittest.TestCase):
    def test_state_preserves_promoted_boundary_without_inferring_canonical(self):
        self.assertEqual(STATE["principal_state"], "PROMOTED")
        self.assertEqual(STATE["gates"]["PROJECTION_TRUTH_CLOSED"]["status"], "PASS")
        self.assertEqual(STATE["gates"]["CANONICAL_POSITION_RESOLVED"]["status"], "PENDING")
        self.assertEqual(STATE["gates"]["EVOLUTION_CURSOR_DEFINED"]["status"], "PASS")

    def test_position_preserves_identity_and_lineage(self):
        self.assertEqual(POSITION["repository"], STATE["repository"])
        policy = POSITION["integration_policy"]
        self.assertEqual(POSITION["position_state"], "RESOLVED")
        self.assertTrue(
            policy["preserve_repository_identity"]
            and policy["preserve_lineage"]
            and policy["presentation_independent"]
        )
        self.assertTrue(
            policy["absorption_requires_functional_equivalence"]
            and policy["absorption_requires_proof_equivalence"]
        )

    def test_evolution_cursor_names_the_unfinished_canonical_gate(self):
        self.assertEqual(
            STATE["evolution_cursor"],
            "next:canonical_position_only_if_estate_role_resolved",
        )
        self.assertTrue(POSITION["next_evolution"])


if __name__ == "__main__":
    unittest.main()
