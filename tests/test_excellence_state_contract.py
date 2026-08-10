import json
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
STATE = json.loads((ROOT / "machine" / "excellence-state.json").read_text(encoding="utf-8"))
TARGET = json.loads((ROOT / "machine" / "target-contract.json").read_text(encoding="utf-8"))
GATES = ["IDENTITY_RESOLVED","PROBLEM_VERIFIED","TARGET_CONTRACT_FROZEN","DONOR_PLAN_RESOLVED","VERTICAL_SLICE_ALIVE","CENTRAL_MECHANISM_PRESENT","DETERMINISTIC_PROOF_GREEN","ADVERSARIAL_SURVIVAL","OPERABLE_AND_OBSERVABLE","PROOF_RECEIPT_BOUND","AUTHORITY_BOUND"]
class ExcellenceStateContractTests(unittest.TestCase):
    def test_promoted_prerequisites(self):
        self.assertEqual(STATE["principal_state"], "PROMOTED")
        for gate in GATES: self.assertEqual(STATE["gates"].get(gate, {}).get("status"), "PASS", gate)
    def test_target_and_donor(self):
        self.assertEqual(TARGET["identity"]["repository_id"], STATE["repository"])
        self.assertEqual(TARGET["current"]["principal_state"], "PROMOTED")
        self.assertEqual(TARGET["donor_plan"]["status"], "RESOLVED")
        self.assertEqual(TARGET["donor_plan"]["strategy"], "INDEPENDENT_MECHANISM_PRESERVED")
    def test_next_gate(self):
        self.assertEqual(STATE["gates"]["CANONICAL_POSITION_RESOLVED"]["status"], "PENDING")
        self.assertIn("canonical_position", STATE["evolution_cursor"])
    def test_nonproduction(self):
        self.assertFalse(TARGET["current"]["deployed"])
        self.assertEqual(STATE["reconciliation"]["previous_state_claim"], "PROMOTED_WITH_PREREQUISITE_GAPS")
if __name__ == "__main__": unittest.main()
