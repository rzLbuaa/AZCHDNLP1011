import json

import httpx
import pytest

from achdnlp.backend import BackendError, HTTPBackend, parse_output
from achdnlp.config import BackendConfig
from achdnlp.schema import Generation


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("ACHDNLP_MODEL", "fixture-model")
    monkeypatch.setenv("ACHDNLP_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("ACHDNLP_API_KEY", "not-a-real-credential")


def envelope(content='{"diagnoses":[],"differential":[]}', reason="stop"):
    return {"choices": [{"message": {"content": content}, "finish_reason": reason}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 10}}


def test_json_contract():
    assert parse_output('```json\n{"diagnoses":[],"differential":[]}\n```', Generation).diagnoses == []
    with pytest.raises(BackendError):
        parse_output('prefix {"diagnoses": []}', Generation)
    with pytest.raises(BackendError):
        parse_output('{"diagnoses":[],"unknown":"field"}', Generation)


def test_authorization_required(env):
    with pytest.raises(ValueError, match="allow-remote"):
        HTTPBackend(BackendConfig(kind="http"))


@pytest.mark.parametrize("url", ["http://remote.example/v1", "https://user:pass@example.invalid", "https://example.invalid?secret=x"])
def test_endpoint_safety(env, monkeypatch, url):
    monkeypatch.setenv("ACHDNLP_BASE_URL", url)
    with pytest.raises(ValueError):
        HTTPBackend(BackendConfig(kind="http"), allow_remote=True)


def test_http_response_and_identity(env):
    requests = []
    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=envelope())
    backend = HTTPBackend(BackendConfig(kind="http"), allow_remote=True,
                          transport=httpx.MockTransport(handler))
    try:
        result = backend.call("generate", {"current_findings": []})
        assert result.diagnoses == []
        assert requests[0]["stream"] is False
        assert len(backend.calls) == 1
        assert "not-a-real-credential" not in json.dumps(backend.identity())
        assert "not-a-real-credential" not in json.dumps(backend.calls)
    finally:
        backend.close()


@pytest.mark.parametrize("body", ["unexpected string", {"choices": []}, {"choices": "bad"},
                                    envelope(reason="length"), envelope(content="not json")])
def test_malformed_responses_are_failures(env, body):
    backend = HTTPBackend(BackendConfig(kind="http"), allow_remote=True,
                          transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body)))
    try:
        with pytest.raises(BackendError):
            backend.call("generate", {})
    finally:
        backend.close()


@pytest.mark.parametrize("status", [400, 401, 403, 404, 302])
def test_nonretryable_errors(env, status):
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(status, json={"detail": "sensitive response body"})
    backend = HTTPBackend(BackendConfig(kind="http"), allow_remote=True,
                          transport=httpx.MockTransport(handler), sleep=lambda _: None)
    try:
        with pytest.raises(BackendError) as exc:
            backend.call("generate", {})
        assert len(seen) == 1
        assert "sensitive" not in str(exc.value)
    finally:
        backend.close()


def test_bounded_retry_and_retry_after(env):
    seen, delays = [], []
    def handler(request):
        seen.append(request)
        if len(seen) == 1:
            return httpx.Response(429, headers={"Retry-After": "1000"})
        return httpx.Response(200, json=envelope())
    backend = HTTPBackend(BackendConfig(kind="http"), allow_remote=True,
                          transport=httpx.MockTransport(handler), sleep=delays.append)
    try:
        backend.call("generate", {})
        assert len(seen) == 2 and delays == [60]
        assert backend.calls[0]["attempts"] == 2
    finally:
        backend.close()


def test_retry_exhaustion(env):
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(503)
    backend = HTTPBackend(BackendConfig(kind="http", attempts=2), allow_remote=True,
                          transport=httpx.MockTransport(handler), sleep=lambda _: None)
    try:
        with pytest.raises(BackendError, match="after 2"):
            backend.call("generate", {})
        assert len(seen) == 2
    finally:
        backend.close()
