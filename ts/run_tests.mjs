import { allowClaim } from "./preview_gate.mjs";
import assert from "node:assert/strict";
assert.equal(allowClaim("PREVIEW", "PRODUCTION_VERIFIED").ok, false);
assert.equal(allowClaim("PRODUCTION", "PRODUCTION_VERIFIED").ok, true);
console.log("ok");
