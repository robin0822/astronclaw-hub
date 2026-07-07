from __future__ import annotations

from app.clients.claw_proxy_base import ClawProxyClient


def session_key(session_id: str) -> str:
    return f"agent:main:main:{session_id}"


class TeamApiClient(ClawProxyClient):
    async def list(self, instance_id: str, session_id: str) -> dict:
        return await self.request("GET", f"/{instance_id}/team?session_key={session_key(session_id)}")
