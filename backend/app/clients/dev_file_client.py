from __future__ import annotations

from typing import Any

from app.clients.claw_proxy_base import ClawProxyClient


class DevFileClient(ClawProxyClient):
    async def list(self, instance_id: str, path: str) -> dict[str, Any]:
        return await self.request("GET", f"/{instance_id}/dev/file/list?path={path}")

    async def content(self, instance_id: str, path: str) -> dict[str, Any]:
        return await self.request("GET", f"/{instance_id}/dev/file/content?path={path}")

    async def save(self, instance_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request("PUT", f"/{instance_id}/dev/file/content", payload)
