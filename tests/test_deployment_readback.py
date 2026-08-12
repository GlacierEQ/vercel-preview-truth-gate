from __future__ import annotations

import json
import unittest

from src.deployment_readback import ProbeSpec, VercelDeploymentVerifier
from src.preview_gate import ClaimStrength, DeployTarget


def transport_for(metadata: dict, pages: dict[str, tuple[int, bytes]]):
    def transport(method, url, headers, data, timeout):
        if "api.vercel.com/v13/deployments/" in url:
            return 200, {"content-type": "application/json"}, json.dumps(metadata).encode()
        for suffix, result in pages.items():
            if url.endswith(suffix):
                return result[0], {}, result[1]
        raise AssertionError(f"unexpected URL: {url}")
    return transport


class DeploymentReadbackTests(unittest.TestCase):
    def test_live_readback_proves_production_source_and_semantics(self):
        sha = "a" * 40
        metadata = {
            "id": "dpl_123",
            "url": "demo.vercel.app",
            "target": "production",
            "meta": {"githubCommitSha": sha},
        }
        verifier = VercelDeploymentVerifier(
            "token",
            team_id="team_1",
            transport=transport_for(
                metadata,
                {
                    "/": (200, b"hello production"),
                    "/api/health": (200, b'{"ok":true,"version":3}'),
                },
            ),
            clock=lambda: 1234.0,
        )
        receipt = verifier.verify(
            "demo.vercel.app",
            sha,
            [
                ProbeSpec("homepage", "/", 200, body_contains="production"),
                ProbeSpec("health", "/api/health", 200, json_path="ok", json_equals=True),
            ],
            expected_target=DeployTarget.PRODUCTION,
        )
        self.assertTrue(receipt.decision.allowed)
        self.assertEqual(receipt.observed_source_sha, sha)
        self.assertIs(receipt.target, DeployTarget.PRODUCTION)
        self.assertTrue(all(p.passed for p in receipt.probes))
        self.assertEqual(len(receipt.fingerprint), 64)

    def test_source_mismatch_refuses_even_when_http_probes_pass(self):
        metadata = {
            "id": "dpl_123",
            "url": "demo.vercel.app",
            "target": "production",
            "meta": {"githubCommitSha": "b" * 40},
        }
        verifier = VercelDeploymentVerifier(
            "token", transport=transport_for(metadata, {"/": (200, b"ok")})
        )
        receipt = verifier.verify(
            "demo.vercel.app",
            "a" * 40,
            [ProbeSpec("homepage", "/", 200, body_contains="ok")],
        )
        self.assertFalse(receipt.decision.allowed)
        self.assertEqual(receipt.decision.reason, "SOURCE_SHA_MISMATCH")

    def test_failed_live_probe_refuses_production_verified_claim(self):
        sha = "c" * 40
        metadata = {
            "id": "dpl_123",
            "url": "demo.vercel.app",
            "target": "production",
            "meta": {"githubCommitSha": sha},
        }
        verifier = VercelDeploymentVerifier(
            "token",
            transport=transport_for(metadata, {"/api/health": (503, b'{"ok":false}')}),
        )
        receipt = verifier.verify(
            "demo.vercel.app",
            sha,
            [ProbeSpec("health", "/api/health", 200, json_path="ok", json_equals=True)],
        )
        self.assertFalse(receipt.decision.allowed)
        self.assertEqual(receipt.decision.reason, "SEMANTIC_INVARIANT_FAILED:health")
        self.assertEqual(receipt.probes[0].status, 503)

    def test_preview_metadata_cannot_mint_production_verified_claim(self):
        sha = "d" * 40
        metadata = {
            "id": "dpl_123",
            "url": "demo.vercel.app",
            "target": None,
            "meta": {"githubCommitSha": sha},
        }
        verifier = VercelDeploymentVerifier(
            "token", transport=transport_for(metadata, {"/": (200, b"ok")})
        )
        receipt = verifier.verify(
            "demo.vercel.app",
            sha,
            [ProbeSpec("homepage", "/", 200, body_contains="ok")],
            requested_strength=ClaimStrength.PRODUCTION_VERIFIED,
        )
        self.assertIs(receipt.target, DeployTarget.PREVIEW)
        self.assertFalse(receipt.decision.allowed)
        self.assertEqual(receipt.decision.reason, "TARGET_PREVIEW_MAX_TESTED")

    def test_metadata_request_is_authenticated_and_team_scoped(self):
        captured = {}
        sha = "e" * 40
        metadata = {
            "id": "dpl_1",
            "url": "demo.vercel.app",
            "target": "production",
            "meta": {"githubCommitSha": sha},
        }

        def transport(method, url, headers, data, timeout):
            captured.update({"method": method, "url": url, "headers": headers})
            return 200, {}, json.dumps(metadata).encode()

        verifier = VercelDeploymentVerifier("secret", team_id="team_X", transport=transport)
        result = verifier.get_deployment("demo.vercel.app")
        self.assertEqual(result["id"], "dpl_1")
        self.assertEqual(captured["method"], "GET")
        self.assertIn("teamId=team_X", captured["url"])
        self.assertEqual(captured["headers"]["Authorization"], "Bearer secret")


if __name__ == "__main__":
    unittest.main()
