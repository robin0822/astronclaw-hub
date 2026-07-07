from __future__ import annotations

from app.models import BackupTask, now_utc


def process_backup_if_mock(task: BackupTask) -> None:
    if task.status not in {"running", "queued"}:
        return
    task.status = "success"
    task.phase = "completed"
    task.ended_at = now_utc()


def backup_task_dto(task: BackupTask) -> dict:
    return {
        "taskId": task.id,
        "agentId": task.agent_id,
        "type": task.type,
        "proxyTaskId": task.proxy_task_id,
        "status": task.status,
        "phase": task.phase,
        "startedAt": task.started_at.isoformat() if task.started_at else None,
        "endedAt": task.ended_at.isoformat() if task.ended_at else None,
    }
