from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings
from app.core.errors import (
    BOT_DEPLOY_FAILED,
    BusinessError,
    CLAW_PROXY_TIMEOUT,
    SANDBOX_SESSION_EXPIRED,
)

SENSITIVE_KEY_MARKERS = ("token", "apikey", "api_key", "api-secret", "api_secret", "secret", "password", "authorization")


class ClawProxyClient:
    def __init__(self, base_url: str | None = None, token: str | None = None, timeout: float = 10.0, retries: int = 1) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.claw_proxy_base_url).rstrip("/")
        self.token = token or settings.claw_proxy_auth_token
        self.timeout = timeout
        self.retries = retries

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    async def request(self, method: str, path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}/api/v1/bot{path}"
        attempts = max(self.retries, 0) + 1
        last_timeout: httpx.TimeoutException | None = None
        for _ in range(attempts):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(method, url, headers=self.headers(), json=json)
                return self.parse_response(response)
            except httpx.TimeoutException as exc:
                last_timeout = exc
                continue
            except httpx.HTTPError as exc:
                raise BusinessError(CLAW_PROXY_TIMEOUT, "claw proxy timeout", 502) from exc
        raise BusinessError(CLAW_PROXY_TIMEOUT, "claw proxy timeout", 504) from last_timeout

    def parse_response(self, response: httpx.Response) -> dict[str, Any]:
        if response.status_code in {400, 404}:
            raise BusinessError(
                SANDBOX_SESSION_EXPIRED,
                "sandbox session expired",
                502,
                {"reason": "sandbox_session_expired", "retryAdvice": "sync instance status or redeploy the agent"},
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise BusinessError(CLAW_PROXY_TIMEOUT, "claw proxy timeout", 502) from exc
        code = payload.get("code", 0)
        if code in (0, "0", None):
            return payload.get("data", payload)
        sanitized = sanitize_external_payload(payload, self.token)
        if str(code) == "400003":
            raise BusinessError(
                SANDBOX_SESSION_EXPIRED,
                "sandbox session expired",
                502,
                sanitized | {"reason": "sandbox_session_expired", "retryAdvice": "sync instance status or redeploy the agent"},
            )
        if str(code) == "300003":
            raise BusinessError(BOT_DEPLOY_FAILED, "bot deploy failed", 502, sanitized)
        raise BusinessError(CLAW_PROXY_TIMEOUT, safe_external_message(payload.get("message"), self.token), 502, sanitized)


def mask_token(token: str) -> str:
    if len(token) <= 8:
        return token[:2] + "***"
    return token[:4] + "***" + token[-4:]


def sanitize_external_payload(value: Any, token: str | None = None) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if is_sensitive_key(key):
                result[key] = "[masked]"
            else:
                result[key] = sanitize_external_payload(item, token)
        return result
    if isinstance(value, list):
        return [sanitize_external_payload(item, token) for item in value]
    if isinstance(value, str):
        return safe_external_message(value, token)
    return value


def safe_external_message(value: Any, token: str | None = None) -> str:
    text = str(value or "claw proxy error")
    if token:
        text = text.replace(token, "[masked]")
    parts = []
    for raw in text.split():
        if any(marker in raw.lower() for marker in SENSITIVE_KEY_MARKERS):
            parts.append("[masked]")
        else:
            parts.append(raw)
    return " ".join(parts)


def is_sensitive_key(key: str) -> bool:
    normalized = key.replace("-", "_").lower()
    return any(marker.replace("-", "_") in normalized for marker in SENSITIVE_KEY_MARKERS)
