# Vercel Preview Truth Readback

Independent GlacierEQ deployment-verification utility for proving what code and behavior are actually live on a Vercel deployment.

## Purpose

A preview URL, a green build, or a caller-supplied boolean does not prove production truth. This repository performs the readback itself:

```text
Vercel deployment ID / URL
        ↓
authenticated deployment metadata
        ↓
operational origin / canonical alias
        ↓
source identity from metadata OR named runtime response header
        ↓
live HTTP semantic probes
        ↓
deterministic verification receipt
        ↓
claim strength decision
```

The existing environment-ceiling model remains intact: Preview cannot mint a Production Verified claim, Staging cannot exceed its deployment ceiling, and Production Verified requires exact source identity plus passing semantic invariants.

## Real readback paths

`src/deployment_readback.py` supports:

- authenticated `GET /v13/deployments/{idOrUrl}` against the Vercel REST API;
- optional `teamId` scoping;
- deployed Git SHA extraction from Vercel metadata when present;
- production alias selection when Vercel's unique deployment hostname is protected or noncanonical;
- explicit `--origin` override when a specific runtime origin must be probed;
- runtime source-SHA fallback from an explicitly named response header such as `x-glaciereq-source-commit`;
- disagreement detection when metadata SHA and runtime-header SHA both exist but differ;
- live HTTP status, body-text, and JSON-path semantic probes;
- latency and response-body SHA-256 observations;
- deterministic metadata and final receipt fingerprints.

The runtime-header fallback exists because real Vercel deployments may be operationally valid while the deployment metadata exposed to a client does not contain a Git SHA. That gap must be resolved from observed runtime evidence, not by inventing a source identity.

## Live verification

```bash
export VERCEL_TOKEN='...'
export VERCEL_TEAM_ID='team_...'
```

Metadata carries Git SHA:

```bash
python scripts/verify_deployment_claim.py \
  --deployment my-app.vercel.app \
  --target PRODUCTION \
  --expected-sha "$GITHUB_SHA" \
  --probe 'homepage,/,200,contains=Expected Heading' \
  --probe 'health,/api/health,200,json=ok:true'
```

Runtime carries Git SHA instead:

```bash
python scripts/verify_deployment_claim.py \
  --deployment dpl_... \
  --origin https://my-app.vercel.app \
  --target PRODUCTION \
  --expected-sha "$GITHUB_SHA" \
  --source-header x-glaciereq-source-commit \
  --source-path / \
  --probe 'homepage,/,200,contains=Expected Heading'
```

The command exits `0` only when the requested claim is supported. It exits non-zero on source drift, unreadable source headers, metadata/runtime source disagreement, failed probes, target mismatch, malformed evidence, missing credentials, or Vercel metadata failure.

## Compatibility mode

Existing CI jobs that already extracted trusted evidence upstream remain supported:

```bash
python scripts/verify_deployment_claim.py \
  --target PRODUCTION \
  --strength PRODUCTION_VERIFIED \
  --expected-sha abc123 \
  --observed-sha abc123 \
  --check homepage=true
```

Live readback is stronger because the verifier obtains operational observations itself.

## Run the proof suite

```bash
python -m unittest discover -s tests -v
python scripts/operate.py
```

`operate.py` deliberately models the harder real condition: production metadata lacks Git SHA, the unique hostname is not the desired operational origin, a canonical alias is selected, and source identity is recovered from a runtime response header before semantic probes are admitted.

## Architecture

| Surface | Responsibility |
|---|---|
| `src/preview_gate.py` | Claim-strength ceilings and deterministic evidence decisions |
| `src/deployment_readback.py` | Vercel metadata, runtime source identity, origin resolution, live probes |
| `scripts/verify_deployment_claim.py` | Live and compatibility CLI |
| `scripts/operate.py` | Full metadata-gap executable demonstration |
| `tests/test_deployment_readback.py` | Source, alias, probe, target, authentication behavior |

## Operational boundary

This repository is a CLI/library, not a hosted application, so its natural completion target is a reproducible verifier used by deployment pipelines. A Production Verified receipt still requires a real target deployment, source identity, and meaningful semantic probes. Missing facts remain missing; the tool does not promote around them.

This project is not affiliated with or endorsed by Vercel. It uses documented public Vercel APIs and explicitly declared runtime evidence surfaces.
