import crypto from "node:crypto";

const RANK = { MARKETING: 0, TESTED: 1, DEPLOYED: 2, PRODUCTION_VERIFIED: 3 };
const MAX = { PREVIEW: "TESTED", STAGING: "DEPLOYED", PRODUCTION: "PRODUCTION_VERIFIED" };
const TARGETS = new Set(Object.keys(MAX));
const STRENGTHS = new Set(Object.keys(RANK));
const CHECK_NAME = /^[A-Za-z0-9_.:-]+$/;
const SOURCE_REF = /^[A-Za-z0-9_.:/-]+$/;

function canonical(value) {
  if (value === null || typeof value === "boolean" || typeof value === "string") return JSON.stringify(value);
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new Error("non-finite JSON number");
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (typeof value === "object") {
    return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonical(value[key])}`).join(",")}}`;
  }
  throw new Error("unsupported JSON value");
}

function fingerprint(value) {
  return crypto.createHash("sha256").update(canonical(value), "utf8").digest("hex");
}

function normalizeEvidence(evidence) {
  if (evidence === null || typeof evidence !== "object" || Array.isArray(evidence))
    throw new Error("evidence must be an object");
  const expected = evidence.expected_source_sha;
  const observed = evidence.observed_source_sha;
  if (typeof expected !== "string" || !SOURCE_REF.test(expected))
    throw new Error("expected_source_sha must be a non-empty machine-safe source ref");
  if (typeof observed !== "string" || !SOURCE_REF.test(observed))
    throw new Error("observed_source_sha must be a non-empty machine-safe source ref");
  const checks = evidence.semantic_checks;
  if (checks === null || typeof checks !== "object" || Array.isArray(checks))
    throw new Error("semantic_checks must be an object");
  const normalizedChecks = {};
  for (const name of Object.keys(checks).sort()) {
    if (!CHECK_NAME.test(name)) throw new Error("semantic check names must be non-empty machine-safe tokens");
    if (typeof checks[name] !== "boolean") throw new Error("semantic check results must be boolean");
    normalizedChecks[name] = checks[name];
  }
  return {
    expected_source_sha: expected,
    observed_source_sha: observed,
    semantic_checks: normalizedChecks,
  };
}

export function maxClaimFor(target) {
  if (!TARGETS.has(target)) throw new Error("unknown deploy target");
  return MAX[target];
}

export function evaluateClaim(target, strength, evidence = null) {
  if (!TARGETS.has(target)) throw new Error("unknown deploy target");
  if (!STRENGTHS.has(strength)) throw new Error("unknown claim strength");
  const mx = maxClaimFor(target);
  let reason = null;
  let normalizedEvidence = null;
  if (evidence !== null) normalizedEvidence = normalizeEvidence(evidence);

  if (RANK[strength] > RANK[mx]) {
    reason = `TARGET_${target}_MAX_${mx}`;
  } else if (strength === "PRODUCTION_VERIFIED") {
    if (target !== "PRODUCTION") reason = "PRODUCTION_TARGET_REQUIRED";
    else if (normalizedEvidence === null) reason = "EVIDENCE_REQUIRED";
    else if (normalizedEvidence.expected_source_sha !== normalizedEvidence.observed_source_sha)
      reason = "SOURCE_SHA_MISMATCH";
    else if (Object.keys(normalizedEvidence.semantic_checks).length === 0)
      reason = "SEMANTIC_INVARIANT_REQUIRED";
    else {
      const failed = Object.entries(normalizedEvidence.semantic_checks)
        .filter(([, passed]) => !passed)
        .map(([name]) => name)
        .sort();
      if (failed.length) reason = `SEMANTIC_INVARIANT_FAILED:${failed.join(",")}`;
    }
  }

  const evidenceFingerprint = normalizedEvidence === null ? null : fingerprint(normalizedEvidence);
  const payload = {
    target,
    strength,
    max_target_strength: mx,
    allowed: reason === null,
    reason,
    evidence_fingerprint: evidenceFingerprint,
    evidence: normalizedEvidence,
    boundary: "target ceiling is not proof of lower-strength execution",
  };
  return {
    ok: reason === null,
    allowed: reason === null,
    reason,
    maxTargetStrength: mx,
    evidenceFingerprint,
    fingerprint: fingerprint(payload),
  };
}

export function allowClaim(target, strength, evidence = null) {
  return evaluateClaim(target, strength, evidence);
}
