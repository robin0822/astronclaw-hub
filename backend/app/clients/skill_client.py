from __future__ import annotations

from typing import Any

from app.clients.claw_proxy_base import ClawProxyClient


class SkillClient(ClawProxyClient):
    async def list(self, instance_id: str) -> dict[str, Any]:
        return await self.request("GET", f"/{instance_id}/skill/list")

    async def install(self, instance_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request("POST", f"/{instance_id}/skill/install", payload)

    async def uninstall(self, instance_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request("POST", f"/{instance_id}/skill/uninstall", payload)

    async def add_env(self, instance_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request("POST", f"/{instance_id}/skill/add_env", payload)

    async def remove_env(self, instance_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request("POST", f"/{instance_id}/skill/remove_env", payload)
