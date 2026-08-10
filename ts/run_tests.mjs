import assert from "node:assert/strict";
import { allowClaim, evaluateClaim } from "./preview_gate.mjs";

assert.equal(allowClaim("PREVIEW", "PRODUCTION_VERIFIED").ok, false);
assert.equal(allowClaim("STAGING", "PRODUCTION_VERIFIED").reason, "TARGET_STAGING_MAX_DEPLOYED");

const missing = allowClaim("PRODUCTION", "PRODUCTION_VERIFIED");
assert.equal(missing.ok, false);
assert.equal(missing.reason, "EVIDENCE_REQUIRED");

const mismatch = allowClaim("PRODUCTION", "PRODUCTION_VERIFIED", {
  expected_source_sha: "sha_expected",
  observed_source_sha: "sha_observed",
  semantic_checks: { homepage_resume_match: true },
});
assert.equal(mismatch.reason, "SOURCE_SHA_MISMATCH");

const emptyChecks = allowClaim("PRODUCTION", "PRODUCTION_VERIFIED", {
  expected_source_sha: "sha_abc",
  observed_source_sha: "sha_abc",
  semantic_checks: {},
});
assert.equal(emptyChecks.reason, "SEMANTIC_INVARIANT_REQUIRED");

const failed = allowClaim("PRODUCTION", "PRODUCTION_VERIFIED", {
  expected_source_sha: "sha_abc",
  observed_source_sha: "sha_abc",
  semantic_checks: { machine_contract_match: true, homepage_resume_match: false },
});
assert.equal(failed.reason, "SEMANTIC_INVARIANT_FAILED:homepage_resume_match");

const evidence = {
  expected_source_sha: "sha_abc",
  observed_source_sha: "sha_abc",
  semantic_checks: { machine_contract_match: true, homepage_resume_match: true },
};
const allowed = evaluateClaim("PRODUCTION", "PRODUCTION_VERIFIED", evidence);
assert.equal(allowed.ok, true);
assert.equal(allowed.reason, null);
assert.equal(allowed.fingerprint.length, 64);
assert.equal(allowed.evidenceFingerprint.length, 64);

const reordered = evaluateClaim("PRODUCTION", "PRODUCTION_VERIFIED", {
  observed_source_sha: "sha_abc",
  expected_source_sha: "sha_abc",
  semantic_checks: { homepage_resume_match: true, machine_contract_match: true },
});
assert.equal(allowed.fingerprint, reordered.fingerprint);

assert.throws(
  () => allowClaim("PRODUCTION", "PRODUCTION_VERIFIED", {
    expected_source_sha: "sha_abc",
    observed_source_sha: "sha_abc",
    semantic_checks: { homepage_resume_match: "yes" },
  }),
  /must be boolean/,
);
assert.throws(() => allowClaim("UNKNOWN", "TESTED"), /unknown deploy target/);
assert.throws(() => allowClaim("PREVIEW", "UNKNOWN"), /unknown claim strength/);

const lower = allowClaim("PRODUCTION", "DEPLOYED");
assert.equal(lower.ok, true);

console.log("ok");
