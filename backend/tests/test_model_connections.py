import asyncio
import json

import httpx
import pytest

from model_platform.administration_models import ModelConnection
from model_platform.errors import Problem
from model_platform.services import model_connections


def connection(admin):
    result = admin.post("/api/v1/admin/model-connections", json={"name": "思考模型兼容", "endpoint": "https://api.example.com/v1", "model": "reasoning-test", "secret": "private-probe-secret"})
    assert result.status_code == 201
    return result.json()["data"]["id"]


def response_provider(monkeypatch, payload, requests):
    original = httpx.AsyncClient

    def provider(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=payload)

    monkeypatch.setattr(model_connections, "validate_remote", lambda endpoint: None)
    monkeypatch.setattr(model_connections.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(provider), **kwargs))


@pytest.mark.parametrize("content", ["", '{"samples":['])
def test_truncated_reasoning_or_partial_answer_has_precise_error(app, admin, monkeypatch, content):
    identifier = connection(admin)
    response_provider(monkeypatch, {"choices": [{"finish_reason": "length", "message": {"content": content, "reasoning_content": "private-reasoning-text"}}]}, [])
    with app.state.sessions() as db:
        item = db.get(ModelConnection, identifier)
        with pytest.raises(Problem) as caught:
            asyncio.run(model_connections.completion(app.state.settings, item, [{"role": "user", "content": "Reply with OK."}], max_tokens=8))
        assert caught.value.code == "PROVIDER_OUTPUT_LIMIT"
        assert "private-reasoning-text" not in caught.value.message and "private-probe-secret" not in caught.value.message


def test_connection_probe_has_reasoning_budget_and_distinguishes_reachability(admin, monkeypatch):
    identifier, requests = connection(admin), []
    response_provider(monkeypatch, {"choices": [{"finish_reason": "length", "message": {"content": "", "reasoning_content": "thinking"}}]}, requests)
    result = admin.post(f"/api/v1/admin/model-connections/{identifier}/test").json()["data"]
    assert requests[0]["max_tokens"] == 256
    assert result["health"]["status"] == "available"
    assert result["health"]["code"] == "PROVIDER_OUTPUT_LIMIT"
    assert isinstance(result["health"]["elapsed_ms"], int) and result["health"]["elapsed_ms"] >= 0


def test_empty_non_truncated_response_remains_invalid(admin, monkeypatch):
    identifier = connection(admin)
    response_provider(monkeypatch, {"choices": [{"finish_reason": "stop", "message": {"content": ""}}]}, [])
    result = admin.post(f"/api/v1/admin/model-connections/{identifier}/test").json()["data"]
    assert result["health"]["status"] == "failed" and result["health"]["code"] == "PROVIDER_INVALID_RESPONSE"
