from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Agent,
    AgentBindSkill,
    AgentDeployTask,
    BatchTask,
    BatchTaskItem,
    BusinessSystem,
    BusinessSystemAgentGrant,
    ChannelBindAgent,
    SeatAssignment,
    SeatPackage,
    ShareGrant,
    Skill,
    now_utc,
)


def process_agent_task_if_mock(db: Session, task: AgentDeployTask) -> None:
    if task.status not in {"queued", "running"}:
        return
    agent = db.get(Agent, task.agent_id)
    if not agent:
        task.status = "failed"
        task.error_code = "AGENT_NOT_FOUND"
        task.error_message = "agent not found"
        task.progress = 100
        task.ended_at = now_utc()
        return

    task.status = "running"
    task.started_at = task.started_at or now_utc()
    task.node = task.node or "local-mock-worker"
    task.phase = task.action

    if task.action == "deploy":
        failure_mode = (agent.resource_spec or {}).get("_mockDeployFailure")
        if failure_mode in {"300003", "deploy_failed"}:
            _fail_agent_task(
                agent,
                task,
                error_code="502003",
                error_message="Claw Proxy bot deploy failed: upstream code 300003",
                retry_advice="Check skill package, model config and sandbox logs, then retry deploy.",
            )
            return
        if failure_mode in {"timeout", "502001"}:
            _fail_agent_task(
                agent,
                task,
                error_code="502001",
                error_message="Claw Proxy timeout after retry threshold",
                retry_advice="Check Claw Proxy network reachability and retry after the sandbox service recovers.",
            )
            return

    if task.action in {"deploy", "start"}:
        agent.proxy_instance_id = agent.proxy_instance_id or f"sandbox-{agent.bot_id}"
        agent.status = "running"
        if task.action == "deploy":
            failed_skills = _install_bound_skills(db, agent)
            if failed_skills:
                agent.status = "abnormal"
                task.status = "failed"
                task.phase = "skill_install"
                task.progress = 100
                task.error_code = "SKILL_INSTALL_FAILED"
                task.error_message = f"Skill install failed: {', '.join(item['skillId'] for item in failed_skills)}"
                task.retry_advice = "Review failed skill packages and retry deployment after fixing package or permission issues."
                task.ended_at = now_utc()
                return
    elif task.action == "stop":
        agent.status = "stopped"
    elif task.action == "restart":
        agent.status = "running"
    elif task.action == "upgrade":
        agent.status = "running"
    elif task.action == "archive":
        agent.status = "archived"
        _release_agent_resources(db, agent)
    elif task.action == "violation-offline":
        agent.status = "violation_offline"

    task.status = "success"
    task.phase = "completed"
    task.progress = 100
    task.ended_at = now_utc()


def _fail_agent_task(agent: Agent, task: AgentDeployTask, error_code: str, error_message: str, retry_advice: str) -> None:
    agent.status = "abnormal"
    task.status = "failed"
    task.phase = "deploy"
    task.progress = 100
    task.error_code = error_code
    task.error_message = error_message
    task.retry_advice = retry_advice
    task.ended_at = now_utc()


def _install_bound_skills(db: Session, agent: Agent) -> list[dict[str, str | None]]:
    rows = db.execute(select(AgentBindSkill).where(AgentBindSkill.agent_id == agent.id)).scalars().all()
    failure_targets = set((agent.resource_spec or {}).get("_mockSkillInstallFailure") or [])
    failed: list[dict[str, str | None]] = []
    for row in rows:
        skill = db.get(Skill, row.skill_id)
        package_name = skill.package_name if skill else row.package_name
        if row.skill_id in failure_targets or package_name in failure_targets:
            row.status = "failed"
            failed.append({"skillId": row.skill_id, "packageName": package_name})
            continue
        row.status = "installed"
        if skill:
            row.package_name = skill.package_name
            row.installed_version = skill.version
    return failed


def process_batch_if_mock(db: Session, batch: BatchTask) -> None:
    if batch.status not in {"queued", "running"}:
        return
    items = db.execute(select(BatchTaskItem).where(BatchTaskItem.batch_task_id == batch.id)).scalars().all()
    batch.status = "running"
    pause_on_failure = bool((batch.strategy or {}).get("pauseOnFailure", False))
    batch_size = int((batch.strategy or {}).get("batchSize") or len(items) or 1)
    processed_this_run = 0
    for item in items:
        if item.status in {"success", "failed", "skipped"}:
            continue
        if processed_this_run >= batch_size:
            continue
        item.started_at = item.started_at or now_utc()
        agent = db.get(Agent, item.target_id)
        if not agent:
            item.status = "failed"
            item.error_code = "AGENT_NOT_FOUND"
            item.error_message = "agent not found"
        else:
            _apply_batch_action(db, agent, item.action)
            item.status = "success"
        item.ended_at = now_utc()
        processed_this_run += 1
        if item.status == "failed" and pause_on_failure:
            break
    _refresh_batch_counts(batch, items)
    if pause_on_failure and batch.failed_count > 0 and any(item.status == "queued" for item in items):
        batch.status = "paused"
    elif batch.success_count + batch.failed_count + batch.skipped_count < batch.total:
        batch.status = "running"
    else:
        batch.status = "success" if batch.failed_count == 0 else "partial_success"


def _refresh_batch_counts(batch: BatchTask, items: list[BatchTaskItem]) -> None:
    batch.success_count = sum(1 for item in items if item.status == "success")
    batch.failed_count = sum(1 for item in items if item.status == "failed")
    batch.skipped_count = sum(1 for item in items if item.status == "skipped")


def _apply_batch_action(db: Session, agent: Agent, action: str) -> None:
    if action in {"deploy", "start"}:
        agent.proxy_instance_id = agent.proxy_instance_id or f"sandbox-{agent.bot_id}"
        agent.status = "running"
    elif action == "stop":
        agent.status = "stopped"
    elif action == "restart":
        agent.status = "running"
    elif action == "archive":
        agent.status = "archived"
        _release_agent_resources(db, agent)
    elif action == "delete":
        _release_agent_resources(db, agent)
        agent.deleted_at = now_utc()


def _release_agent_resources(db: Session, agent: Agent) -> None:
    seats = db.execute(
        select(SeatAssignment).where(
            SeatAssignment.assignee_type == "agent",
            SeatAssignment.agent_id == agent.id,
            SeatAssignment.status == "active",
        )
    ).scalars().all()
    for seat in seats:
        pkg = db.get(SeatPackage, seat.seat_package_id)
        if pkg and pkg.used_count > 0:
            pkg.used_count -= 1
        seat.status = "reclaimed"

    for bind in db.execute(select(ChannelBindAgent).where(ChannelBindAgent.agent_id == agent.id, ChannelBindAgent.status == "active")).scalars().all():
        bind.status = "disabled"

    for grant in db.execute(select(BusinessSystemAgentGrant).where(BusinessSystemAgentGrant.agent_id == agent.id, BusinessSystemAgentGrant.status == "active")).scalars().all():
        grant.status = "disabled"
        system = db.get(BusinessSystem, grant.business_system_id)
        if system and agent.id in (system.allowed_agent_ids or []):
            system.allowed_agent_ids = [item for item in (system.allowed_agent_ids or []) if item != agent.id]

    for grant in db.execute(select(ShareGrant).where(ShareGrant.agent_id == agent.id, ShareGrant.status == "active")).scalars().all():
        grant.status = "revoked"
