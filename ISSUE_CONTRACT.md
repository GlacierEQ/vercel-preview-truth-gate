# ISSUE CONTRACT
## Pain
Preview/staging context can be misread as production truth, and language surfaces can disagree on what `PRODUCTION_VERIFIED` requires.

## Success
- Preview ceiling: at most `TESTED`
- Staging ceiling: at most `DEPLOYED`
- Production ceiling: `PRODUCTION_VERIFIED` only with exact source readback plus at least one named semantic invariant
- Semantic invariant results are explicit booleans, never truthy coercions
- Python and Node enforce the same production-verification rule
- Decision receipt binds target, requested strength, target ceiling, evidence identity, and terminal reason

## Boundary
A target ceiling is an authorization limit, not proof that a lower-strength action actually occurred. This reference gate does not deploy, fetch external Vercel state, or claim Vercel affiliation/adoption.
