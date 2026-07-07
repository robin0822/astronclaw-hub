from __future__ import annotations

from typing import Any

from app.clients.claw_proxy_base import ClawProxyClient


class CronProxy(ClawProxyClient):
    async def create(self, instance_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request("POST", f"/{instance_id}/cron", payload)

    async def update(self, instance_id: str, cron_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request("PUT", f"/{instance_id}/cron/{cron_id}", payload)

    async def delete(self, instance_id: str, cron_id: str) -> dict[str, Any]:
        return await self.request("DELETE", f"/{instance_id}/cron/{cron_id}")
