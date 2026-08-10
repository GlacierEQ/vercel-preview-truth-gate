# Substance boundary

This repository survives as an independent component only if it enforces deployment-truth invariants in executable release paths.

## Runtime contract

Input:
- deployment target
- requested claim strength
- intended source commit SHA
- observed source commit SHA from deployed readback
- named semantic invariant results

Output:
- allow/refuse decision
- explicit refusal reason
- deterministic evidence-bound fingerprint
- non-zero process exit on refusal through `scripts/verify_deployment_claim.py`

## Non-goals

This is not a deployment platform, hosting provider integration, or claim of Vercel affiliation. It is a provider-agnostic release gate designed to be embedded in CI/CD after deployment readback.

## Survival gate

Archive or harvest this repo if it stops providing executable exact-SHA/readback enforcement that is independently reusable outside the portfolio site. Documentation, receipts, and CI scaffolding alone do not satisfy this gate.
