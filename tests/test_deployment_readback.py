from __future__ import annotations

import json
import unittest

from src.deployment_readback import ProbeSpec, VercelDeploymentVerifier
from src.preview_gate import ClaimStrength, DeployTarget


def transport_for(metadata: dict, pages: dict[str, tuple[int, dict[str, str], bytes]]):
    def transport(method, url, headers, data, timeout):
        if "api.vercel.com/v13/deployments/" in url:
            return 200, {"content-type": "application/json"}, json.dumps(metadata).encode()
        for suffix, result in pages.items():
            if url.endswith(suffix):
                return result
        raise AssertionError(f"unexpected URL: {url}")
    return transport


class DeploymentReadbackTests(unittest.TestCase):
    def test_live_readback_proves_production_source_and_semantics(self):
        sha = "a" * 40
        metadata = {"id": "dpl_123", "url": "demo.vercel.app", "target": "production", "meta": {"githubCommitSha": sha}}
        verifier = VercelDeploymentVerifier(
            "token",
            team_id="team_1",
            transport=transport_for(
                metadata,
                {
                    "/": (200, {}, b"hello production"),
                    "/api/health": (200, {}, b'{"ok":true,"version":3}'),
                },
            ),
            clock=lambda: 1234.0,
        )
        receipt = verifier.verify(
            "demo.vercel.app",
            sha,
            [ProbeSpec("homepage", "/", 200, body_contains="production"), ProbeSpec("health", "/api/health", 200, json_path="ok", json_equals=True)],
            expected_target=DeployTarget.PRODUCTION,
        )
        self.assertTrue(receipt.decision.allowed)
        self.assertEqual(receipt.observed_source_sha, sha)
        self.assertEqual(receipt.source_identity_method, "vercel_metadata")

    def test_runtime_source_header_closes_metadata_gap(self):
        sha = "9" * 40
        metadata = {"id": "dpl_live", "url": "protected.vercel.app", "alias": ["canonical.vercel.app"], "target": "production", "meta": {}}
        verifier = VercelDeploymentVerifier(
            "token",
            transport=transport_for(metadata, {"/": (200, {"X-GlacierEQ-Source-Commit": sha}, b"Casey Barton Forward-Deployed AI Architect")}),
            clock=lambda: 1234.0,
        )
        receipt = verifier.verify(
            "protected.vercel.app",
            sha,
            [ProbeSpec("homepage", "/", 200, body_contains="Forward-Deployed AI Architect")],
            expected_target=DeployTarget.PRODUCTION,
            source_header="x-glaciereq-source-commit",
        )
        self.assertTrue(receipt.decision.allowed)
        self.assertEqual(receipt.observed_source_sha, sha)
        self.assertEqual(receipt.source_identity_method, "runtime_header")
        self.assertEqual(receipt.deployment_url, "https://canonical.vercel.app")
        self.assertEqual(receipt.source_observation.value, sha)

    def test_explicit_origin_overrides_protected_deployment_hostname(self):
        sha = "8" * 40
        metadata = {"id": "dpl_live", "url": "protected.vercel.app", "target": "production", "meta": {}}
        verifier = VercelDeploymentVerifier(
            "token",
            transport=transport_for(metadata, {"/": (200, {"x-source": sha}, b"ready")}),
        )
        receipt = verifier.verify(
            "protected.vercel.app",
            sha,
            [ProbeSpec("homepage", "/", 200, body_contains="ready")],
            runtime_origin="https://public.example",
            source_header="x-source",
        )
        self.assertTrue(receipt.decision.allowed)
        self.assertEqual(receipt.deployment_url, "https://public.example")

    def test_metadata_runtime_source_disagreement_fails_semantic_check(self):
        metadata_sha = "a" * 40
        runtime_sha = "b" * 40
        metadata = {"id": "dpl_123", "url": "demo.vercel.app", "target": "production", "meta": {"githubCommitSha": metadata_sha}}
        verifier = VercelDeploymentVerifier(
            "token",
            transport=transport_for(metadata, {"/": (200, {"x-source": runtime_sha}, b"ok")}),
        )
        receipt = verifier.verify(
            "demo.vercel.app",
            runtime_sha,
            [ProbeSpec("homepage", "/", 200, body_contains="ok")],
            source_header="x-source",
        )
        self.assertFalse(receipt.decision.allowed)
        self.assertEqual(receipt.decision.reason, "SEMANTIC_INVARIANT_FAILED:metadata_runtime_source_match")

    def test_source_mismatch_refuses_even_when_http_probes_pass(self):
        metadata = {"id": "dpl_123", "url": "demo.vercel.app", "target": "production", "meta": {"githubCommitSha": "b" * 40}}
        verifier = VercelDeploymentVerifier("token", transport=transport_for(metadata, {"/": (200, {}, b"ok")}))
        receipt = verifier.verify("demo.vercel.app", "a" * 40, [ProbeSpec("homepage", "/", 200, body_contains="ok")])
        self.assertFalse(receipt.decision.allowed)
        self.assertEqual(receipt.decision.reason, "SOURCE_SHA_MISMATCH")

    def test_failed_live_probe_refuses_production_verified_claim(self):
        sha = "c" * 40
        metadata = {"id": "dpl_123", "url": "demo.vercel.app", "target": "production", "meta": {"githubCommitSha": sha}}
        verifier = VercelDeploymentVerifier("token", transport=transport_for(metadata, {"/api/health": (503, {}, b'{"ok":false}')}))
        receipt = verifier.verify("demo.vercel.app", sha, [ProbeSpec("health", "/api/health", 200, json_path="ok", json_equals=True)])
        self.assertFalse(receipt.decision.allowed)
        self.assertEqual(receipt.decision.reason, "SEMANTIC_INVARIANT_FAILED:health")

    def test_preview_metadata_cannot_mint_production_verified_claim(self):
        sha = "d" * 40
        metadata = {"id": "dpl_123", "url": "demo.vercel.app", "target": None, "meta": {"githubCommitSha": sha}}
        verifier = VercelDeploymentVerifier("token", transport=transport_for(metadata, {"/": (200, {}, b"ok")}))
        receipt = verifier.verify("demo.vercel.app", sha, [ProbeSpec("homepage", "/", 200, body_contains="ok")], requested_strength=ClaimStrength.PRODUCTION_VERIFIED)
        self.assertIs(receipt.target, DeployTarget.PREVIEW)
        self.assertFalse(receipt.decision.allowed)
        self.assertEqual(receipt.decision.reason, "TARGET_PREVIEW_MAX_TESTED")

    def test_metadata_request_is_authenticated_and_team_scoped(self):
        captured = {}
        metadata = {"id": "dpl_1", "url": "demo.vercel.app", "target": "production", "meta": {"githubCommitSha": "e" * 40}}
        def transport(method, url, headers, data, timeout):
            captured.update({"method": method, "url": url, "headers": headers})
            return 200, {}, json.dumps(metadata).encode()
        verifier = VercelDeploymentVerifier("secret", team_id="team_X", transport=transport)
        result = verifier.get_deployment("demo.vercel.app")
        self.assertEqual(result["id"], "dpl_1")
        self.assertIn("teamId=team_X", captured["url"])
        self.assertEqual(captured["headers"]["Authorization"], "Bearer secret")


if __name__ == "__main__":
    unittest.main()
