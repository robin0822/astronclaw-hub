from __future__ import annotations

from typing import Any

from app.clients.claw_proxy_base import ClawProxyClient


class BotClient(ClawProxyClient):
    async def deploy(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request("POST", "/deploy", payload)

    async def stop(self, instance_id: str) -> dict[str, Any]:
        return await self.request("POST", f"/{instance_id}/stop")

    async def restart(self, instance_id: str) -> dict[str, Any]:
        return await self.request("POST", f"/{instance_id}/restart")

    async def upgrade(self, instance_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request("POST", f"/{instance_id}/upgrade", payload)

    async def switch_model(self, instance_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request("PUT", f"/{instance_id}/model", payload)

    async def doctor_fix(self, instance_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request("POST", f"/{instance_id}/doctor/fix", payload)
