import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = json.loads(
    (ROOT / "machine" / "excellence-state.json").read_text(encoding="utf-8")
)
POSITION = json.loads(
    (ROOT / "machine" / "canonical-position.json").read_text(encoding="utf-8")
)
PROOF = json.loads(
    (ROOT / "machine" / "canonical-position-proof.json").read_text(encoding="utf-8")
)


class ExcellenceStateContractTests(unittest.TestCase):
    def test_state_advances_only_after_exact_canonical_proof(self):
        self.assertEqual(STATE["principal_state"], "EVOLVING")
        self.assertEqual(STATE["state"], "EVOLVING")
        self.assertEqual(
            STATE["gates"]["PROJECTION_TRUTH_CLOSED"]["status"], "PASS"
        )
        self.assertEqual(
            STATE["gates"]["CANONICAL_POSITION_RESOLVED"]["status"], "PASS"
        )
        self.assertEqual(
            STATE["gates"]["EVOLUTION_CURSOR_DEFINED"]["status"], "PASS"
        )
        self.assertEqual(PROOF["workflow"]["conclusion"], "success")

    def test_position_preserves_identity_and_lineage(self):
        self.assertEqual(POSITION["repository"], STATE["repository"])
        policy = POSITION["integration_policy"]
        self.assertEqual(POSITION["position_state"], "RESOLVED")
        self.assertEqual(POSITION["canonical_identity"], "preview-truth-gate")
        self.assertTrue(
            policy["preserve_repository_identity"]
            and policy["preserve_lineage"]
            and policy["presentation_independent"]
        )
        self.assertTrue(
            policy["absorption_requires_functional_equivalence"]
            and policy["absorption_requires_proof_equivalence"]
        )

    def test_evolution_cursor_names_the_next_real_mechanism(self):
        self.assertEqual(
            STATE["evolution_cursor"],
            "next:compose_evidence_graph_claim_compiler_receipts_and_add_divergence_revocation",
        )
        self.assertTrue(POSITION["next_evolution"])
        self.assertIn("revocation", POSITION["next_evolution"].lower())


if __name__ == "__main__":
    unittest.main()
