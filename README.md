# Vercel Preview Truth Readback

Independent GlacierEQ deployment-verification utility for proving what code and behavior are actually live on a Vercel deployment.

## Purpose

A preview URL, a green build, or a caller-supplied boolean does not prove production truth. This repository now performs the readback itself:

```text
Vercel deployment ID / URL
        ↓
authenticated deployment metadata
        ↓
observed deployed Git SHA
        ↓
live HTTP semantic probes
        ↓
source + behavior evidence
        ↓
deterministic verification receipt
        ↓
claim strength decision
```

The existing environment-ceiling model remains intact: Preview cannot mint a Production Verified claim, Staging cannot exceed its deployment ceiling, and Production Verified requires exact source identity plus passing semantic invariants.

## What is real now

`src/deployment_readback.py` adds:

- authenticated `GET /v13/deployments/{idOrUrl}` readback against the Vercel REST API;
- optional team scoping with `teamId`;
- deployed Git SHA extraction from Vercel deployment metadata;
- target inference from deployment metadata;
- live HTTP probes against the actual deployment URL;
- expected status checks;
- required body-content checks;
- JSON-path equality checks;
- latency and response-body SHA-256 observations;
- deterministic metadata and final receipt fingerprints;
- fail-closed source mismatch and semantic drift behavior.

## Live verification

Set credentials without committing them:

```bash
export VERCEL_TOKEN='...'
export VERCEL_TEAM_ID='team_...'
```

Then verify a deployment:

```bash
python scripts/verify_deployment_claim.py \
  --deployment my-app.vercel.app \
  --target PRODUCTION \
  --strength PRODUCTION_VERIFIED \
  --expected-sha "$GITHUB_SHA" \
  --probe 'homepage,/,200,contains=Expected Heading' \
  --probe 'health,/api/health,200,json=ok:true'
```

The command exits `0` only when the requested claim is supported. It exits non-zero on source drift, failed probes, target mismatch, malformed evidence, missing credentials, or Vercel metadata failure.

Extra request headers can be supplied with repeated `--header NAME=VALUE` arguments for protected/readback environments.

## Compatibility mode

Existing CI jobs that already extracted trusted readback data upstream still work:

```bash
python scripts/verify_deployment_claim.py \
  --target PRODUCTION \
  --strength PRODUCTION_VERIFIED \
  --expected-sha abc123 \
  --observed-sha abc123 \
  --check homepage=true \
  --check machine_contract=true
```

This mode is preserved for compatibility. **Live Vercel readback is the stronger path** because the verifier obtains the deployment metadata and semantic observations itself.

## Run the proof suite

```bash
python -m unittest discover -s tests -v
python scripts/operate.py
```

`operate.py` uses an injected deterministic transport to exercise the complete metadata → source readback → live probe → claim-decision pipeline without network credentials. The production transport uses Python's standard HTTPS stack and requires a Vercel access token.

## Architecture

| Surface | Responsibility |
|---|---|
| `src/preview_gate.py` | Claim-strength ceilings and deterministic evidence decisions |
| `src/deployment_readback.py` | Real Vercel metadata retrieval and deployment HTTP probes |
| `scripts/verify_deployment_claim.py` | Live/compatibility CLI |
| `scripts/operate.py` | Full executable demonstration |
| `tests/test_deployment_readback.py` | Source, probe, target, and authentication behavior tests |

## Completion boundary

This repository is a verification tool, not a hosted application, so its natural operational form is a runnable CLI/library used by deployment pipelines. It does not need to deploy itself to Vercel to fulfill its purpose.

A **live Production Verified receipt still requires an actual target deployment, `VERCEL_TOKEN`, an expected source SHA, and at least one meaningful semantic probe**. The repository does not fabricate that receipt in their absence.

## Non-claims

This project is not affiliated with or endorsed by Vercel. It uses documented public Vercel APIs and makes no claim of proprietary access.
