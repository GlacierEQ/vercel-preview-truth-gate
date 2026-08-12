"""Live Vercel deployment readback and semantic probe engine.

The verifier obtains Vercel deployment metadata, resolves an operational origin,
reads source identity from deployment metadata or an explicitly named runtime
response header, executes semantic HTTP probes, and binds observations into a
deterministic receipt before evaluating claim strength.
"""
from __future__ import annotations

import hashlib
import json
import ssl
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urljoin
from urllib.request import Request, urlopen

from .preview_gate import (
    ClaimStrength,
    DeployTarget,
    DeploymentEvidence,
    GateDecision,
    evaluate_claim,
)


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def _normalize_url(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("deployment URL is required")
    if not value.startswith(("https://", "http://")):
        value = "https://" + value
    return value.rstrip("/")


def _extract_git_sha(metadata: Mapping[str, Any]) -> str | None:
    meta = metadata.get("meta")
    candidates: list[Any] = [metadata.get("gitCommitSha"), metadata.get("githubCommitSha")]
    if isinstance(meta, Mapping):
        candidates.extend(
            [
                meta.get("githubCommitSha"),
                meta.get("gitCommitSha"),
                meta.get("VERCEL_GIT_COMMIT_SHA"),
                meta.get("vercelGitCommitSha"),
            ]
        )
    git_source = metadata.get("gitSource")
    if isinstance(git_source, Mapping):
        candidates.extend([git_source.get("sha"), git_source.get("ref")])
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _infer_target(metadata: Mapping[str, Any]) -> DeployTarget:
    raw = metadata.get("target")
    if isinstance(raw, str):
        normalized = raw.lower()
        if normalized == "production":
            return DeployTarget.PRODUCTION
        if normalized in {"staging", "stage"}:
            return DeployTarget.STAGING
    return DeployTarget.PREVIEW


def _runtime_origin(metadata: Mapping[str, Any], deployment: str, override: str | None) -> str:
    if override:
        return _normalize_url(override)
    if _infer_target(metadata) is DeployTarget.PRODUCTION:
        aliases = metadata.get("alias")
        if isinstance(aliases, Sequence) and not isinstance(aliases, (str, bytes, bytearray)):
            for alias in aliases:
                if isinstance(alias, str) and alias.strip():
                    return _normalize_url(alias)
    raw = metadata.get("url")
    return _normalize_url(str(raw or deployment))


def _header(headers: Mapping[str, str], name: str) -> str | None:
    wanted = name.lower()
    for key, value in headers.items():
        if key.lower() == wanted:
            return value.strip() if isinstance(value, str) else str(value)
    return None


@dataclass(frozen=True)
class ProbeSpec:
    name: str
    path: str = "/"
    expected_status: int = 200
    body_contains: str | None = None
    json_path: str | None = None
    json_equals: Any = None
    timeout_s: float = 10.0

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("probe name is required")
        if not self.path.startswith("/"):
            raise ValueError("probe path must start with /")
        if not 100 <= self.expected_status <= 599:
            raise ValueError("expected_status must be a valid HTTP status")
        if self.timeout_s <= 0 or self.timeout_s > 120:
            raise ValueError("timeout_s must be in (0, 120]")
        if self.json_path is None and self.json_equals is not None:
            raise ValueError("json_equals requires json_path")


@dataclass(frozen=True)
class ProbeObservation:
    name: str
    url: str
    passed: bool
    status: int | None
    latency_ms: float
    body_sha256: str | None
    reason: str | None
    observed_value: Any = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SourceObservation:
    url: str
    header_name: str
    value: str | None
    status: int | None
    body_sha256: str | None
    reason: str | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DeploymentReadbackReceipt:
    deployment_url: str
    deployment_id: str | None
    target: DeployTarget
    expected_source_sha: str
    observed_source_sha: str | None
    source_identity_method: str
    metadata_source_sha: str | None
    metadata_fingerprint: str
    source_observation: SourceObservation | None
    probes: tuple[ProbeObservation, ...]
    decision: GateDecision
    created_at: float
    fingerprint: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "deployment_url": self.deployment_url,
            "deployment_id": self.deployment_id,
            "target": self.target.value,
            "expected_source_sha": self.expected_source_sha,
            "observed_source_sha": self.observed_source_sha,
            "source_identity_method": self.source_identity_method,
            "metadata_source_sha": self.metadata_source_sha,
            "metadata_fingerprint": self.metadata_fingerprint,
            "source_observation": self.source_observation.as_dict() if self.source_observation else None,
            "probes": [p.as_dict() for p in self.probes],
            "decision": {
                "allowed": self.decision.allowed,
                "reason": self.decision.reason,
                "max_target_strength": self.decision.max_target_strength.value,
                "evidence_fingerprint": self.decision.evidence_fingerprint,
                "fingerprint": self.decision.fingerprint,
            },
            "created_at": self.created_at,
            "fingerprint": self.fingerprint,
        }


class VercelApiError(RuntimeError):
    def __init__(self, status: int | None, message: str, body: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.body = body


Transport = Callable[[str, str, Mapping[str, str], bytes | None, float], tuple[int, Mapping[str, str], bytes]]


def _default_transport(method: str, url: str, headers: Mapping[str, str], data: bytes | None, timeout: float) -> tuple[int, Mapping[str, str], bytes]:
    req = Request(url=url, method=method, headers=dict(headers), data=data)
    try:
        with urlopen(req, timeout=timeout, context=ssl.create_default_context()) as response:
            return response.status, dict(response.headers.items()), response.read()
    except HTTPError as exc:
        return exc.code, dict(exc.headers.items()) if exc.headers else {}, exc.read()
    except URLError as exc:
        raise VercelApiError(None, f"network_error:{exc.reason}") from exc


class VercelDeploymentVerifier:
    API_BASE = "https://api.vercel.com"

    def __init__(self, token: str, *, team_id: str | None = None, transport: Transport | None = None, clock: Callable[[], float] | None = None) -> None:
        if not token.strip():
            raise ValueError("Vercel access token is required for deployment metadata readback")
        self._token = token.strip()
        self._team_id = team_id.strip() if team_id else None
        self._transport = transport or _default_transport
        self._clock = clock or time.time

    def get_deployment(self, id_or_url: str) -> dict[str, Any]:
        if not id_or_url.strip():
            raise ValueError("deployment id or URL is required")
        query = urlencode({"teamId": self._team_id}) if self._team_id else ""
        endpoint = f"{self.API_BASE}/v13/deployments/{quote(id_or_url.strip(), safe='')}"
        if query:
            endpoint += "?" + query
        status, _headers, body = self._transport(
            "GET",
            endpoint,
            {
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/json",
                "User-Agent": "GlacierEQ-Vercel-Truth-Readback/1.1",
            },
            None,
            15.0,
        )
        text = body.decode("utf-8", errors="replace")
        if status != 200:
            raise VercelApiError(status, f"vercel_metadata_http_{status}", text[:1000])
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise VercelApiError(status, "vercel_metadata_invalid_json", text[:1000]) from exc
        if not isinstance(parsed, dict):
            raise VercelApiError(status, "vercel_metadata_not_object", text[:1000])
        return parsed

    @staticmethod
    def _json_path(value: Any, path: str) -> Any:
        current = value
        for segment in path.split("."):
            if isinstance(current, Mapping) and segment in current:
                current = current[segment]
            elif isinstance(current, Sequence) and not isinstance(current, (str, bytes, bytearray)) and segment.isdigit():
                current = current[int(segment)]
            else:
                raise KeyError(path)
        return current

    def read_source_header(self, deployment_url: str, header_name: str, *, path: str = "/", headers: Mapping[str, str] | None = None, timeout_s: float = 10.0) -> SourceObservation:
        if not header_name.strip():
            raise ValueError("source header name must not be blank")
        if not path.startswith("/"):
            raise ValueError("source path must start with /")
        base = _normalize_url(deployment_url) + "/"
        url = urljoin(base, path.lstrip("/"))
        request_headers = {
            "Accept": "*/*",
            "User-Agent": "GlacierEQ-Vercel-Truth-Readback/1.1",
            **dict(headers or {}),
        }
        try:
            status, response_headers, body = self._transport("GET", url, request_headers, None, timeout_s)
            value = _header(response_headers, header_name)
            reason = None
            if status >= 400:
                reason = f"source_readback_http_{status}"
            elif not value:
                reason = "source_header_missing"
            return SourceObservation(
                url=url,
                header_name=header_name,
                value=value,
                status=status,
                body_sha256=hashlib.sha256(body).hexdigest(),
                reason=reason,
            )
        except Exception as exc:
            return SourceObservation(
                url=url,
                header_name=header_name,
                value=None,
                status=None,
                body_sha256=None,
                reason=f"request_error:{type(exc).__name__}:{exc}",
            )

    def run_probe(self, deployment_url: str, spec: ProbeSpec, *, headers: Mapping[str, str] | None = None) -> ProbeObservation:
        base = _normalize_url(deployment_url) + "/"
        url = urljoin(base, spec.path.lstrip("/"))
        request_headers = {
            "Accept": "application/json,text/plain,text/html,*/*",
            "User-Agent": "GlacierEQ-Vercel-Truth-Readback/1.1",
            **dict(headers or {}),
        }
        started = time.perf_counter()
        try:
            status, _response_headers, body = self._transport("GET", url, request_headers, None, spec.timeout_s)
            latency_ms = round((time.perf_counter() - started) * 1000.0, 3)
            digest = hashlib.sha256(body).hexdigest()
            reason: str | None = None
            observed: Any = None
            if status != spec.expected_status:
                reason = f"status:{status}!={spec.expected_status}"
            text = body.decode("utf-8", errors="replace")
            if reason is None and spec.body_contains is not None and spec.body_contains not in text:
                reason = "body_missing_required_text"
            if reason is None and spec.json_path is not None:
                try:
                    payload = json.loads(text)
                    observed = self._json_path(payload, spec.json_path)
                except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
                    reason = f"json_path_unreadable:{type(exc).__name__}"
                else:
                    if observed != spec.json_equals:
                        reason = "json_value_mismatch"
            return ProbeObservation(spec.name, url, reason is None, status, latency_ms, digest, reason, observed)
        except Exception as exc:
            return ProbeObservation(
                spec.name,
                url,
                False,
                None,
                round((time.perf_counter() - started) * 1000.0, 3),
                None,
                f"request_error:{type(exc).__name__}:{exc}",
            )

    def verify(
        self,
        deployment: str,
        expected_source_sha: str,
        probes: Sequence[ProbeSpec],
        *,
        requested_strength: ClaimStrength = ClaimStrength.PRODUCTION_VERIFIED,
        expected_target: DeployTarget | None = None,
        deployment_headers: Mapping[str, str] | None = None,
        runtime_origin: str | None = None,
        source_header: str | None = None,
        source_path: str = "/",
    ) -> DeploymentReadbackReceipt:
        if not expected_source_sha.strip():
            raise ValueError("expected_source_sha is required")
        if not probes:
            raise ValueError("at least one live semantic probe is required")

        metadata = self.get_deployment(deployment)
        target = _infer_target(metadata)
        deployment_url = _runtime_origin(metadata, deployment, runtime_origin)
        deployment_id = str(metadata.get("id")) if metadata.get("id") else None
        metadata_fp = _digest(metadata)
        metadata_sha = _extract_git_sha(metadata)

        source_observation: SourceObservation | None = None
        runtime_sha: str | None = None
        if source_header:
            source_observation = self.read_source_header(
                deployment_url,
                source_header,
                path=source_path,
                headers=deployment_headers,
            )
            runtime_sha = source_observation.value if source_observation.reason is None else None

        observed_sha = runtime_sha or metadata_sha
        if runtime_sha:
            source_method = "runtime_header"
        elif metadata_sha:
            source_method = "vercel_metadata"
        else:
            source_method = "missing"

        observations = tuple(self.run_probe(deployment_url, spec, headers=deployment_headers) for spec in probes)
        checks = {probe.name: probe.passed for probe in observations}
        if expected_target is not None:
            checks["target_matches_expected"] = target is expected_target
        if source_header:
            checks["runtime_source_header_readable"] = runtime_sha is not None
        if runtime_sha and metadata_sha:
            checks["metadata_runtime_source_match"] = runtime_sha == metadata_sha

        evidence = DeploymentEvidence(
            expected_source_sha=expected_source_sha,
            observed_source_sha=observed_sha or "MISSING_SOURCE_READBACK",
            semantic_checks=checks,
        )
        decision = evaluate_claim(target, requested_strength, evidence)
        created_at = self._clock()
        receipt_body = {
            "deployment_url": deployment_url,
            "deployment_id": deployment_id,
            "target": target.value,
            "expected_source_sha": expected_source_sha,
            "observed_source_sha": observed_sha,
            "source_identity_method": source_method,
            "metadata_source_sha": metadata_sha,
            "metadata_fingerprint": metadata_fp,
            "source_observation": source_observation.as_dict() if source_observation else None,
            "probes": [p.as_dict() for p in observations],
            "decision_fingerprint": decision.fingerprint,
            "created_at": created_at,
        }
        return DeploymentReadbackReceipt(
            deployment_url=deployment_url,
            deployment_id=deployment_id,
            target=target,
            expected_source_sha=expected_source_sha,
            observed_source_sha=observed_sha,
            source_identity_method=source_method,
            metadata_source_sha=metadata_sha,
            metadata_fingerprint=metadata_fp,
            source_observation=source_observation,
            probes=observations,
            decision=decision,
            created_at=created_at,
            fingerprint=_digest(receipt_body),
        )
