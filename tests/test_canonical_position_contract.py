from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path: str):
    text = (ROOT / path).read_text()
    for marker in ("<<<<<<<", "=======", ">>>>>>>"):
        if marker in text:
            raise AssertionError(f"unresolved conflict marker in {path}: {marker}")
    return json.loads(text)


CANONICAL = load("machine/canonical-position.json")
CAPABILITIES = load("machine/capabilities.json")
TARGET = load("machine/target-contract.json")
STATE = load("machine/excellence-state.json")
PROOF = load("machine/canonical-position-proof.json")


class CanonicalPositionContractTests(unittest.TestCase):
    def test_repository_owns_environment_truth_gate(self):
        self.assertEqual(CANONICAL["position_state"], "RESOLVED")
        self.assertEqual(CANONICAL["role"], "CANONICAL_SPECIALIST")
        self.assertEqual(
            CANONICAL["owns"], "environment_bound_production_claim_truth_gate"
        )
        self.assertEqual(CANONICAL["canonical_identity"], "preview-truth-gate")

    def test_deploy_claim_compiler_relationship_is_not_integrated(self):
        edge = CANONICAL["relationships"][0]
        self.assertEqual(
            edge["repository"], "GlacierEQ/vercel-deploy-claim-compiler"
        )
        self.assertFalse(edge["integration_exercised"])

    def test_capabilities_are_repository_native(self):
        capabilities = set(CAPABILITIES["capabilities"])
        self.assertNotIn("hyper-scaling", capabilities)
        self.assertIn("environment_bound_claim_ceiling", capabilities)
        self.assertIn("exact_source_readback_guard", capabilities)
        self.assertIn("strict_boolean_semantic_invariant_gate", capabilities)
        self.assertIn("python_node_production_truth_parity", capabilities)

    def test_target_contract_is_conflict_free_and_evolving(self):
        self.assertEqual(TARGET["current"]["state"], "EVOLVING")
        self.assertTrue(TARGET["current"]["canonical_position_resolved"])
        self.assertFalse(TARGET["current"]["deployed"])
        self.assertFalse(TARGET["donor_plan"]["integration_exercised"])

    def test_excellence_state_closes_canonical_gate(self):
        self.assertEqual(STATE["principal_state"], "EVOLVING")
        self.assertEqual(STATE["state"], "EVOLVING")
        self.assertEqual(
            STATE["gates"]["CANONICAL_POSITION_RESOLVED"]["status"], "PASS"
        )

    def test_proof_binds_exact_tested_source_and_run(self):
        self.assertEqual(
            PROOF["source_sha"],
            "9a3076ba71a6792ea452681fa0f532663635fb4e",
        )
        self.assertEqual(PROOF["workflow"]["run_id"], 31401313384)
        self.assertEqual(PROOF["workflow"]["conclusion"], "success")
        self.assertEqual(set(PROOF["workflow"]["jobs"]), {"py", "node"})

    def test_truth_boundary_separates_ceiling_from_execution_proof(self):
        boundary = CAPABILITIES["truth_boundary"]
        self.assertIn("do not prove lower-strength testing or deployment", boundary)
        self.assertIn("does not deploy", boundary)
        self.assertIn("Vercel affiliation/adoption", boundary)


if __name__ == "__main__":
    unittest.main()
