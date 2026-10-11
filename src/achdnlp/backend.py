import json
import os
import time
from collections.abc import Callable
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ValidationError

from .capsule import prompt
from .config import BackendConfig
from .io import canonical_json, digest
from .schema import Generation, RawCandidate, Sentence, Verification, Verdict


class BackendError(RuntimeError):
    pass


def parse_output(text: str, schema: type[BaseModel]):
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        if lines[0] in {"```", "```json"}:
            text = "\n".join(lines[1:-1]).strip()
    try:
        return schema.model_validate_json(text)
    except (ValidationError, ValueError):
        raise BackendError("response violates the declared JSON schema") from None


class DemoBackend:
    kind = "demo"

    def __init__(self, ontology, rules):
        self.ontology, self.rules = ontology, rules
        self.calls: list[dict] = []

    def identity(self) -> dict:
        return {"kind": "demo", "model": "deterministic-rule-fixture-v1"}

    def call(self, stage: str, payload: dict):
        self.calls.append({"stage": stage, "request_hash": digest(payload), "attempts": 1,
                           "model": self.identity()["model"], "elapsed_seconds": 0.0,
                           "data_origin": "demonstration"})
        current = [Sentence(**s, start=0, end=len(s["text"])) for s in payload["current_findings"]]
        if stage == "generate":
            items = self.rules.hypotheses(current, self.ontology.concepts)
            for prior in payload.get("label_priors", [])[:1]:
                code = prior["identifier"]
                if not any(item.identifier == code for item in items):
                    items.append(RawCandidate(identifier=code, name=self.ontology.concepts[code].name,
                                               certainty="definite"))
            return Generation(diagnoses=items)
        result = []
        for candidate in payload["candidates"]:
            support = self.rules.support(candidate["identifier"], current)
            status = {"definite": "supported", "possible": "uncertain", "negated": "unsupported",
                      "historical": "historical"}.get(support.status, "uncertain")
            result.append(Verdict(candidate_id=candidate["candidate_id"], status=status,
                                  evidence=list(support.evidence), reason="deterministic fixture"))
        return Verification(verdicts=result)

    def close(self) -> None:
        return None


class HTTPBackend:
    kind = "http"

    def __init__(self, config: BackendConfig, *, allow_remote: bool = False,
                 transport=None, sleep: Callable[[float], None] = time.sleep):
        if not allow_remote:
            raise ValueError("remote inference requires explicit --allow-remote authorization")
        self.config = config
        self.model = os.environ.get(config.model_env, "").strip()
        self.base_url = os.environ.get(config.base_url_env, "").rstrip("/")
        key = os.environ.get(config.api_key_env, "")
        url = urlsplit(self.base_url)
        if not self.model or not self.base_url or not key:
            raise ValueError("model, base URL and API-key environment variables are required")
        if url.username or url.password or url.query or url.fragment:
            raise ValueError("base URL must not contain credentials, query strings or fragments")
        local = url.hostname in {"127.0.0.1", "localhost", "::1"}
        if url.scheme != "https" and not (local and config.allow_local_http and url.scheme == "http"):
            raise ValueError("HTTPS is required except for explicitly allowed local services")
        self.client = httpx.Client(
            headers={"Authorization": f"Bearer {key}"},
            timeout=httpx.Timeout(config.timeout_seconds, connect=15),
            follow_redirects=False, trust_env=False, transport=transport,
        )
        self.sleep = sleep
        self.calls: list[dict] = []

    def identity(self) -> dict:
        return {"kind": "http", "model": self.model, "endpoint": self.base_url,
                "parameters": self.config.model_dump(exclude={"api_key_env"})}

    def call(self, stage: str, payload: dict):
        schema = Generation if stage == "generate" else Verification
        request = {"model": self.model, "messages": [
            {"role": "system", "content": prompt(stage)},
            {"role": "user", "content": canonical_json(payload)},
        ], self.config.token_parameter: self.config.max_tokens, "stream": False}
        if self.config.send_temperature:
            request["temperature"] = self.config.temperature
        if self.config.json_mode:
            request["response_format"] = {"type": "json_object"}
        started = time.perf_counter()
        failure = "request_failed"
        for attempt in range(1, self.config.attempts + 1):
            delay = min(2 ** (attempt - 1), 8)
            try:
                response = self.client.post(self.base_url + "/chat/completions", json=request)
                if response.status_code in {408, 429, 500, 502, 503, 504}:
                    failure = f"http_{response.status_code}"
                    retry = response.headers.get("Retry-After", "")
                    if retry.isdigit():
                        delay = min(int(retry), 60)
                elif response.status_code != 200:
                    raise BackendError(f"non-retryable HTTP status {response.status_code}")
                else:
                    body = response.json()
                    if not isinstance(body, dict) or not isinstance(body.get("choices"), list) or not body["choices"]:
                        raise BackendError("invalid chat-completion response envelope")
                    choice = body["choices"][0]
                    if not isinstance(choice, dict) or choice.get("finish_reason") in {"length", "content_filter"}:
                        raise BackendError("incomplete or filtered model response")
                    content = choice.get("message", {}).get("content")
                    if not isinstance(content, str):
                        raise BackendError("chat content must be a JSON string")
                    result = parse_output(content, schema)
                    self.calls.append({"stage": stage, "request_hash": digest(request),
                                       "response_hash": digest(result.model_dump()), "attempts": attempt,
                                       "elapsed_seconds": time.perf_counter() - started,
                                       "model": self.model, "usage": body.get("usage", {})})
                    return result
            except httpx.TransportError:
                failure = "transport_error"
            except (json.JSONDecodeError, AttributeError, KeyError, TypeError):
                raise BackendError("invalid response envelope") from None
            if attempt < self.config.attempts:
                self.sleep(delay)
        raise BackendError(f"{failure} after {self.config.attempts} attempts")

    def close(self) -> None:
        self.client.close()
