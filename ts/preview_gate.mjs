const RANK = { MARKETING: 0, TESTED: 1, DEPLOYED: 2, PRODUCTION_VERIFIED: 3 };
const MAX = { PREVIEW: "TESTED", STAGING: "DEPLOYED", PRODUCTION: "PRODUCTION_VERIFIED" };

export function maxClaimFor(target) { return MAX[target]; }
export function allowClaim(target, strength) {
  const mx = MAX[target];
  if (RANK[strength] <= RANK[mx]) return { ok: true, reason: null };
  return { ok: false, reason: `TARGET_${target}_MAX_${mx}` };
}
