from __future__ import annotations

import httpx

from app.core.config import get_settings
from app.core.errors import BusinessError, CLAW_PROXY_TIMEOUT


class BridgeClient:
    def __init__(self, base_url: str | None = None, token: str | None = None, timeout: float = 10.0) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.bridge_base_url).rstrip("/")
        self.token = token or settings.claw_proxy_auth_token
        self.timeout = timeout

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    async def create_token(self, bot_id: str) -> str:
        if get_settings().mock_external_services:
            return f"bridge_ref_{bot_id}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}/tokens", headers=self.headers(), json={"botId": bot_id})
        except httpx.HTTPError as exc:
            raise BusinessError(CLAW_PROXY_TIMEOUT, "bridge unavailable", 502) from exc
        return self.parse_token_response(response)

    def parse_token_response(self, response: httpx.Response) -> str:
        if response.status_code >= 400:
            raise BusinessError(CLAW_PROXY_TIMEOUT, "bridge unavailable", 502)
        try:
            payload = response.json()
        except ValueError as exc:
            raise BusinessError(CLAW_PROXY_TIMEOUT, "bridge unavailable", 502) from exc
        token = payload.get("bridgeToken") or payload.get("data", {}).get("bridgeToken")
        if not token:
            raise BusinessError(CLAW_PROXY_TIMEOUT, "bridge unavailable", 502)
        return token
