import httpx
import pytest

from app.clients.claw_proxy_base import ClawProxyClient, mask_token
from app.clients.bridge_client import BridgeClient
from app.core.errors import BOT_DEPLOY_FAILED, BusinessError, SANDBOX_SESSION_EXPIRED
from app.clients.team_api_client import session_key


def response(status_code, payload):
    return httpx.Response(status_code, json=payload, request=httpx.Request("GET", "http://test"))


def test_parse_success_response():
    client = ClawProxyClient(base_url="http://proxy", token="secret")
    assert client.parse_response(response(200, {"code": 0, "data": {"instanceId": "ins"}})) == {"instanceId": "ins"}


def test_maps_session_expired():
    client = ClawProxyClient(base_url="http://proxy", token="secret")
    with pytest.raises(BusinessError) as exc:
        client.parse_response(response(200, {"code": 400003, "message": "expired"}))
    assert exc.value.code == SANDBOX_SESSION_EXPIRED
    assert exc.value.data["reason"] == "sandbox_session_expired"
    assert "redeploy" in exc.value.data["retryAdvice"]


@pytest.mark.parametrize("status_code", [400, 404])
def test_maps_http_400_404_to_session_expired_with_recovery_advice(status_code):
    client = ClawProxyClient(base_url="http://proxy", token="secret")
    with pytest.raises(BusinessError) as exc:
        client.parse_response(response(status_code, {"error": "not found"}))
    assert exc.value.code == SANDBOX_SESSION_EXPIRED
    assert exc.value.status_code == 502
    assert exc.value.data == {
        "reason": "sandbox_session_expired",
        "retryAdvice": "sync instance status or redeploy the agent",
    }


def test_maps_deploy_failed():
    client = ClawProxyClient(base_url="http://proxy", token="secret")
    with pytest.raises(BusinessError) as exc:
        client.parse_response(response(200, {"code": 300003, "message": "failed"}))
    assert exc.value.code == BOT_DEPLOY_FAILED


@pytest.mark.parametrize("code", [400003, 300003, 500001])
def test_claw_proxy_error_payload_is_sanitized(code):
    client = ClawProxyClient(base_url="http://proxy", token="service-token-raw")
    payload = {
        "code": code,
        "message": "upstream failed service-token-raw apiKey=sk_live_raw",
        "data": {
            "token": "service-token-raw",
            "apiSecret": "tenant-secret-raw",
            "nested": [{"Authorization": "Bearer service-token-raw"}],
            "safe": "visible",
        },
    }
    with pytest.raises(BusinessError) as exc:
        client.parse_response(response(200, payload))
    combined = f"{exc.value.message} {exc.value.data} {exc.value}"
    assert "service-token-raw" not in combined
    assert "sk_live_raw" not in combined
    assert "tenant-secret-raw" not in combined
    assert exc.value.data["data"]["safe"] == "visible"


def test_mask_token_and_team_session_key():
    assert mask_token("abcdef123456") == "abcd***3456"
    assert session_key("session_x") == "agent:main:main:session_x"


def test_bridge_client_headers_and_success_parse():
    client = BridgeClient(base_url="http://bridge", token="bridge-secret-token")
    headers = client.headers()
    assert headers["Authorization"] == "Bearer bridge-secret-token"
    assert headers["Content-Type"] == "application/json"
    assert client.parse_token_response(response(200, {"bridgeToken": "bridge_ref_123"})) == "bridge_ref_123"


def test_bridge_client_maps_failure_without_leaking_token():
    client = BridgeClient(base_url="http://bridge", token="bridge-secret-token")
    with pytest.raises(BusinessError) as exc:
        client.parse_token_response(response(500, {"error": "bridge-secret-token"}))
    assert exc.value.code
    assert "bridge-secret-token" not in exc.value.message


@pytest.mark.asyncio
async def test_claw_proxy_retries_timeout_then_succeeds(monkeypatch):
    calls = {"count": 0}

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, method, url, headers=None, json=None):
            calls["count"] += 1
            assert headers["Authorization"] == "Bearer retry-secret"
            if calls["count"] == 1:
                raise httpx.TimeoutException("retry-secret")
            return response(200, {"code": 0, "data": {"ok": True}})

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    client = ClawProxyClient(base_url="http://proxy", token="retry-secret", retries=1)
    assert await client.request("GET", "/health") == {"ok": True}
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_claw_proxy_timeout_after_retries_does_not_leak_token(monkeypatch):
    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, method, url, headers=None, json=None):
            raise httpx.TimeoutException("timeout-secret")

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    client = ClawProxyClient(base_url="http://proxy", token="timeout-secret", retries=1)
    with pytest.raises(BusinessError) as exc:
        await client.request("GET", "/health")
    assert exc.value.code == 502001
    assert "timeout-secret" not in exc.value.message
