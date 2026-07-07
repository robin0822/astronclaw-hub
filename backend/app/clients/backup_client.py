from __future__ import annotations

from app.clients.claw_proxy_base import ClawProxyClient


class BackupClient(ClawProxyClient):
    async def start_backup(self, instance_id: str) -> dict:
        return await self.request("POST", f"/{instance_id}/backup")

    async def backup_status(self, instance_id: str, task_id: str) -> dict:
        return await self.request("GET", f"/{instance_id}/backup/status/{task_id}")

    async def start_restore(self, instance_id: str, task_id: str) -> dict:
        return await self.request("POST", f"/{instance_id}/backup/restore/{task_id}")
