from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Header, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import Principal, build_principal, get_current_principal, record_permission_denied, require_permission, token_hash
from app.core.config import get_settings
from app.core.errors import (
    ACCOUNT_DISABLED,
    ACCOUNT_LOCKED,
    APPROVAL_REQUIRED,
    BusinessError,
    CLAW_PROXY_TIMEOUT,
    FORBIDDEN,
    INVALID_STATE,
    PASSWORD_EXPIRED,
    QUOTA_EXCEEDED,
    UNAUTHORIZED,
)
from app.core.pagination import paginate
from app.core.responses import success
from app.core.security import expires_at, hash_password, issue_token, mask_secret, verify_password
from app.id_gen import new_bot_id, new_id
from app.models import (
    Agent,
    AgentBindKnowledge,
    AgentBindSkill,
    AgentCron,
    AgentCronRun,
    AgentDevFileAudit,
    AgentDeployTask,
    AgentLogIndex,
    AgentRuntimeConfig,
    AgentRuntimeSnapshot,
    AgentStateEvent,
    AgentVersion,
    Alert,
    AlertEvent,
    AlertRule,
    ApprovalRequest,
    ApprovalStep,
    AuditLog,
    BackupTask,
    BatchTask,
    BatchTaskItem,
    BusinessSystem,
    BusinessSystemAgentGrant,
    BusinessSystemAuditLog,
    Budget,
    ChannelAuditLog,
    ChannelBindAgent,
    ChannelMessageLog,
    CostDailyStat,
    CostRule,
    Department,
    DiagnosisDecisionTree,
    DiagnosisKb,
    DiagnosisTicket,
    ExportTask,
    FixTask,
    InspectionItem,
    InspectionRun,
    InspectionTask,
    KnowledgeBase,
    KnowledgeFile,
    KnowledgeGrant,
    KnowledgeParseTask,
    LlmModel,
    LoginLog,
    Memory,
    MemoryShareRequest,
    MessageChannel,
    MetricSample,
    ModelCallLog,
    ModelPolicyHit,
    ModelQuotaPolicy,
    ModelRoutePolicy,
    Notification,
    OrgSyncJob,
    Permission,
    Position,
    ResourcePackage,
    Role,
    RolePermission,
    RuntimeSyncJob,
    SeatEvent,
    SeatAssignment,
    SeatPackage,
    SecurityPolicy,
    SensitiveEvent,
    SessionModel,
    ShareGrant,
    Skill,
    SkillEnvVar,
    SkillGrant,
    SkillReview,
    SkillVersion,
    SelfHealTask,
    SsoProvider,
    User,
    UserPosition,
    UserRole,
    now_utc,
)
from app.db import get_db
from app.seed import seed_database
from app.services.audit_integrity import audit_hash_payload
from app.services.backup_service import backup_task_dto, process_backup_if_mock
from app.services.cost_service import archive_costs
from app.services.knowledge_service import create_parse_task, process_parse_task_if_mock, validate_file_security, validate_file_type
from app.services.model_gateway_service import sanitize_summary, simulate_model_call
from app.services.task_service import process_agent_task_if_mock, process_batch_if_mock

router = APIRouter()
settings = get_settings()


Db = Annotated[Session, Depends(get_db)]
Auth = Annotated[Principal, Depends(get_current_principal)]


class LoginRequest(BaseModel):
    username: str
    password: str


class AgentCreateRequest(BaseModel):
    name: str
    type: str = "astronclaw"
    departmentId: str
    ownerId: str
    description: str | None = None
    resourceSpec: dict[str, Any] = Field(default_factory=dict)
    primaryModelId: str
    backupModelId: str | None = None
    concurrencyLimit: int = 20
    dailyCallLimit: int = 10000
    timeoutMs: int = 300000
    skillIds: list[str] = Field(default_factory=list)
    knowledgeBaseIds: list[str] = Field(default_factory=list)
    memoryPolicy: str | None = None
    messageChannelIds: list[str] = Field(default_factory=list)


class BudgetRequest(BaseModel):
    name: str
    scopeType: str
    scopeId: str
    period: str = "monthly"
    limitAmount: float
    thresholdRatio: float = 0.8
    ownerId: str | None = None
    status: str = "active"


class CostRuleRequest(BaseModel):
    name: str
    ruleType: str
    scopeType: str = "global"
    scopeId: str | None = None
    threshold: float = 0
    level: str = "P2"
    status: str = "enabled"
    config: dict[str, Any] = Field(default_factory=dict)


class ResourcePackageRequest(BaseModel):
    name: str
    packageType: str = "container"
    targetType: str = "agent"
    targetId: str | None = None
    cpu: float = 0
    memoryGb: float = 0
    gpu: float = 0
    storageGb: float = 0
    fixedDailyCost: float = 0
    status: str = "active"


def camel_agent(agent: Agent, db: Session) -> dict[str, Any]:
    runtime = agent.runtime or AgentRuntimeSnapshot(agent_id=agent.id)
    department = db.get(Department, agent.department_id) if agent.department_id else None
    owner = db.get(User, agent.owner_id) if agent.owner_id else None
    primary = db.get(LlmModel, agent.primary_model_id) if agent.primary_model_id else None
    backup = db.get(LlmModel, agent.backup_model_id) if agent.backup_model_id else None
    skill_count = db.scalar(select(func.count()).select_from(AgentBindSkill).where(AgentBindSkill.agent_id == agent.id)) or 0
    kb_count = db.scalar(select(func.count()).select_from(AgentBindKnowledge).where(AgentBindKnowledge.agent_id == agent.id)) or 0
    resource = agent.resource_spec or {}
    return {
        "id": agent.id,
        "botId": agent.bot_id,
        "instanceId": agent.proxy_instance_id,
        "name": agent.name,
        "type": agent.type,
        "status": agent.status,
        "version": agent.version,
        "department": _brief(department),
        "owner": _brief(owner),
        "containerCount": runtime.container_count,
        "skillCount": skill_count,
        "knowledgeBaseCount": kb_count,
        "primaryModel": _brief(primary),
        "backupModel": _brief(backup),
        "cpu": resource.get("cpu", runtime.cpu),
        "memory": resource.get("memory", runtime.memory),
        "storage": resource.get("storage", runtime.storage),
        "gpu": resource.get("gpu", runtime.gpu),
        "concurrencyLimit": agent.concurrency_limit,
        "dailyCallLimit": agent.daily_call_limit,
        "timeoutMs": agent.timeout_ms,
        "currentUsers": runtime.current_users,
        "maxUsers": runtime.max_users,
        "qps": runtime.qps,
        "createdAt": _iso(agent.created_at),
        "updatedAt": _iso(agent.updated_at),
    }


def _brief(obj: Any) -> dict[str, Any] | None:
    if not obj:
        return None
    return {"id": obj.id, "name": obj.name}


def _iso(value: Any) -> str | None:
    return value.isoformat() if value else None


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError as exc:
        raise BusinessError(400001, "invalid request", 422, {"field": "time"}) from exc


def _is_future(value: datetime | None) -> bool:
    if not value:
        return False
    current = now_utc()
    if value.tzinfo is None:
        current = current.replace(tzinfo=None)
    return value > current


def password_expired(user: User, max_age_days: int = 90) -> bool:
    if user.identity_source != "local" or not user.password_updated_at:
        return False
    threshold = now_utc() - timedelta(days=max_age_days)
    if user.password_updated_at.tzinfo is None:
        threshold = threshold.replace(tzinfo=None)
    return user.password_updated_at < threshold


def audit(db: Session, actor_id: str | None, module: str, action: str, object_type: str, object_id: str | None, result: str = "success", error: str | None = None, before: dict[str, Any] | None = None, after: dict[str, Any] | None = None) -> None:
    previous = db.execute(select(AuditLog.hash_current).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(1)).scalar_one_or_none() or ""
    created_at = now_utc()
    hash_current = audit_hash_payload(
        hash_prev=previous,
        actor_id=actor_id,
        module=module,
        action=action,
        object_type=object_type,
        object_id=object_id,
        result=result,
        error_message=error,
        before_value=before,
        after_value=after,
        created_at=created_at,
    )
    db.add(
        AuditLog(
            id=new_id("aud"),
            actor_id=actor_id,
            module=module,
            action=action,
            object_type=object_type,
            object_id=object_id,
            result=result,
            error_message=error,
            before_value=before,
            after_value=after,
            hash_prev=previous,
            hash_current=hash_current,
            created_at=created_at,
        )
    )


def record_sensitive_event(
    db: Session,
    actor_id: str | None,
    event_type: str,
    action: str,
    object_type: str,
    object_id: str | None,
    risk_level: str = "high",
    result: str = "success",
    detail: dict[str, Any] | None = None,
) -> SensitiveEvent:
    row = SensitiveEvent(
        id=new_id("sen"),
        actor_id=actor_id,
        event_type=event_type,
        action=action,
        object_type=object_type,
        object_id=object_id,
        risk_level=risk_level,
        result=result,
        detail=detail or {},
    )
    db.add(row)
    return row


def sensitive_event_dto(row: SensitiveEvent) -> dict[str, Any]:
    return {
        "id": row.id,
        "eventType": row.event_type,
        "actorId": row.actor_id,
        "objectType": row.object_type,
        "objectId": row.object_id,
        "action": row.action,
        "riskLevel": row.risk_level,
        "result": row.result,
        "detail": row.detail,
        "createdAt": _iso(row.created_at),
    }


def create_export_task(db: Session, auth: Principal, export_type: str, query: dict[str, Any], approval_id: str | None = None) -> ExportTask:
    task = ExportTask(
        id=new_id("exp"),
        type=export_type,
        status="success",
        applicant_id=auth.user.id,
        approval_id=approval_id,
        query_snapshot=query,
        file_url=f"/api/v1/astron-claw/exports/{export_type}-{new_id('file')}.xlsx",
        watermark=f"{auth.user.username}-{now_utc().date().isoformat()}",
    )
    db.add(task)
    audit(db, auth.user.id, "export", export_type, "export_task", task.id)
    return task


def export_task_dto(task: ExportTask) -> dict[str, Any]:
    return {
        "id": task.id,
        "taskId": task.id,
        "type": task.type,
        "status": task.status,
        "applicantId": task.applicant_id,
        "approvalId": task.approval_id,
        "query": task.query_snapshot,
        "downloadUrl": task.file_url,
        "watermark": task.watermark,
        "createdAt": _iso(task.created_at),
    }


def task_for_agent(db: Session, agent: Agent, action: str, status: str = "queued") -> AgentDeployTask:
    task = AgentDeployTask(id=new_id("task"), agent_id=agent.id, action=action, status=status, phase=action, progress=0)
    db.add(task)
    return task


def agent_config_snapshot(agent: Agent) -> dict[str, Any]:
    return {
        "name": agent.name,
        "description": agent.description,
        "status": agent.status,
        "version": agent.version,
        "departmentId": agent.department_id,
        "ownerId": agent.owner_id,
        "primaryModelId": agent.primary_model_id,
        "backupModelId": agent.backup_model_id,
        "resourceSpec": agent.resource_spec,
        "concurrencyLimit": agent.concurrency_limit,
        "dailyCallLimit": agent.daily_call_limit,
        "timeoutMs": agent.timeout_ms,
        "memoryPolicy": agent.memory_policy,
        "proxyInstanceId": agent.proxy_instance_id,
    }


def add_agent_state_event(db: Session, agent: Agent, from_status: str | None, to_status: str, operator_id: str | None, reason: str | None = None) -> None:
    if from_status == to_status and not reason:
        return
    db.add(AgentStateEvent(id=new_id("ase"), agent_id=agent.id, from_status=from_status, to_status=to_status, operator_id=operator_id, reason=reason))


def add_agent_version(db: Session, agent: Agent, version: str | None = None, rollback_from: str | None = None) -> AgentVersion:
    row = AgentVersion(agent_id=agent.id, version=version or agent.version, config_snapshot=agent_config_snapshot(agent), deployed_at=now_utc(), rollback_from=rollback_from)
    db.add(row)
    return row


def next_agent_version(current: str) -> str:
    parts = current.split(".")
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        parts[2] = str(int(parts[2]) + 1)
        return ".".join(parts)
    return f"{current}.1"


@router.post("/dev/seed")
def dev_seed(db: Db, request: Request):
    seed_database(db)
    return success({"seeded": True}, request.state.request_id)


@router.post("/dev/model-call-logs")
def dev_model_call_log(db: Db, request: Request, payload: dict[str, Any] = Body(...)):
    log = ModelCallLog(
        id=new_id("mcl"),
        user_id=payload.get("userId", "u001"),
        department_id=payload.get("departmentId"),
        project_id=payload.get("projectId"),
        agent_id=payload.get("agentId"),
        model_id=payload.get("modelId", "m001"),
        input_summary=sanitize_summary(payload.get("inputSummary"), "masked input"),
        output_summary=sanitize_summary(payload.get("outputSummary"), "masked output"),
        latency_ms=payload.get("latencyMs", 0),
        tokens=payload.get("tokens", 0),
        cost=payload.get("cost", 0),
        status=payload.get("status", "success"),
        error_code=payload.get("errorCode"),
        created_at=_parse_dt(payload.get("createdAt")) or now_utc(),
    )
    db.add(log)
    db.commit()
    return success({"id": log.id}, request.state.request_id)


@router.post("/dev/model-gateway/call")
def dev_model_gateway_call(db: Db, request: Request, payload: dict[str, Any] = Body(...)):
    result = simulate_model_call(db, payload)
    db.commit()
    if not result["allowed"]:
        raise BusinessError(QUOTA_EXCEEDED, "quota exceeded", 422, result)
    return success(result, request.state.request_id)


@router.post("/dev/cost/archive")
def dev_archive_cost(db: Db, request: Request, payload: dict[str, Any] = Body(default_factory=dict)):
    archive_date = date.fromisoformat(payload["date"]) if payload.get("date") else now_utc().date()
    result = archive_costs(db, archive_date)
    audit(db, None, "cost", "archive", "cost_daily_stats", archive_date.isoformat())
    db.commit()
    return success(result | {"date": archive_date.isoformat()}, request.state.request_id)


@router.post("/auth/login")
def login(payload: LoginRequest, db: Db, request: Request):
    user = db.execute(select(User).where(User.username == payload.username)).scalar_one_or_none()
    if user and user.status != "active":
        db.add(LoginLog(id=new_id("log"), username=payload.username, user_id=user.id, result="failed", failure_reason="account_disabled"))
        db.commit()
        raise BusinessError(ACCOUNT_DISABLED, "account disabled", 401)
    if user and _is_future(user.locked_until):
        db.add(LoginLog(id=new_id("log"), username=payload.username, user_id=user.id, result="failed", failure_reason="account_locked"))
        db.commit()
        raise BusinessError(ACCOUNT_LOCKED, "account locked", 401)
    if not user or not verify_password(payload.password, user.password_hash):
        error_code = UNAUTHORIZED
        error_message = "unauthorized"
        if user:
            user.failed_login_count += 1
            reason = "bad_credentials"
            if user.failed_login_count >= 5:
                user.locked_until = now_utc() + timedelta(minutes=15)
                reason = "account_locked"
                error_code = ACCOUNT_LOCKED
                error_message = "account locked"
        else:
            reason = "bad_credentials"
        db.add(LoginLog(id=new_id("log"), username=payload.username, user_id=user.id if user else None, result="failed", failure_reason=reason))
        db.commit()
        raise BusinessError(error_code, error_message, 401)
    if password_expired(user):
        db.add(LoginLog(id=new_id("log"), username=payload.username, user_id=user.id, result="failed", failure_reason="password_expired"))
        db.commit()
        raise BusinessError(PASSWORD_EXPIRED, "password expired", 401, {"userId": user.id, "passwordUpdatedAt": _iso(user.password_updated_at)})
    principal = build_principal(db, user)
    access_token = issue_token("at")
    refresh_token = issue_token("rt")
    session = SessionModel(
        id=new_id("ses"),
        user_id=user.id,
        access_token_hash=token_hash(access_token),
        refresh_token_hash=token_hash(refresh_token),
        expires_at=now_utc() + timedelta(seconds=settings.access_token_ttl_seconds),
        refresh_expires_at=now_utc() + timedelta(days=7),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now_utc()
    db.add(session)
    db.add(LoginLog(id=new_id("log"), username=user.username, user_id=user.id, result="success"))
    db.commit()
    return success(
        {
            "accessToken": access_token,
            "tokenType": "Bearer",
            "expiresIn": settings.access_token_ttl_seconds,
            "refreshToken": refresh_token,
            "user": user_dto(db, user),
            "roles": principal.roles,
            "permissions": principal.permissions,
            "dataScope": principal.data_scope,
        },
        request.state.request_id,
    )


@router.post("/auth/logout")
def logout(auth: Auth, db: Db, request: Request, authorization: Annotated[str | None, Header()] = None):
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        session = db.execute(select(SessionModel).where(SessionModel.access_token_hash == token_hash(token))).scalar_one_or_none()
        if session:
            session.revoked_at = now_utc()
    audit(db, auth.user.id, "auth", "logout", "session", None)
    db.commit()
    return success({}, request.state.request_id)


@router.post("/auth/refresh")
def refresh_token(db: Db, request: Request, payload: dict[str, Any] = Body(...)):
    session = db.execute(select(SessionModel).where(SessionModel.refresh_token_hash == token_hash(payload.get("refreshToken", "")), SessionModel.revoked_at.is_(None))).scalar_one_or_none()
    if not session:
        raise BusinessError(UNAUTHORIZED, "unauthorized", 401)
    user = db.get(User, session.user_id)
    if not user or user.status != "active":
        raise BusinessError(UNAUTHORIZED, "unauthorized", 401)
    access_token = issue_token("at")
    refresh_token_value = issue_token("rt")
    session.access_token_hash = token_hash(access_token)
    session.refresh_token_hash = token_hash(refresh_token_value)
    session.expires_at = now_utc() + timedelta(seconds=settings.access_token_ttl_seconds)
    session.refresh_expires_at = now_utc() + timedelta(days=7)
    principal = build_principal(db, user)
    audit(db, user.id, "auth", "refresh", "session", session.id)
    db.commit()
    return success({"accessToken": access_token, "tokenType": "Bearer", "expiresIn": settings.access_token_ttl_seconds, "refreshToken": refresh_token_value, "user": user_dto(db, user), "roles": principal.roles, "permissions": principal.permissions, "dataScope": principal.data_scope}, request.state.request_id)


@router.get("/auth/sso/login")
def sso_login(db: Db, request: Request, provider: str = "customer"):
    configured = db.execute(select(SsoProvider).where(SsoProvider.provider == provider)).scalar_one_or_none()
    if configured and configured.status != "enabled":
        raise BusinessError(ACCOUNT_DISABLED, "account disabled", 401, {"provider": provider})
    return success({"provider": provider, "loginUrl": f"/api/v1/astron-claw/auth/sso/callback?provider={provider}"}, request.state.request_id)


@router.get("/auth/sso/callback")
def sso_callback(db: Db, request: Request, provider: str = "customer", subject: str | None = None, username: str | None = None):
    configured = db.execute(select(SsoProvider).where(SsoProvider.provider == provider)).scalar_one_or_none()
    if configured and configured.status != "enabled":
        raise BusinessError(ACCOUNT_DISABLED, "account disabled", 401, {"provider": provider})
    external_subject = subject or username
    if not external_subject:
        raise BusinessError(400001, "invalid request", 422, {"field": "subject"})
    user = db.execute(
        select(User).where(
            (User.sso_subject == external_subject)
            | (User.username == external_subject)
            | (User.employee_no == external_subject)
        )
    ).scalar_one_or_none()
    if not user:
        db.add(LoginLog(id=new_id("log"), username=external_subject, login_type="sso", result="failed", failure_reason="user_not_mapped"))
        db.commit()
        raise BusinessError(UNAUTHORIZED, "unauthorized", 401)
    if user.status != "active":
        db.add(LoginLog(id=new_id("log"), username=user.username, user_id=user.id, login_type="sso", result="failed", failure_reason="account_disabled"))
        db.commit()
        raise BusinessError(ACCOUNT_DISABLED, "account disabled", 401)
    principal = build_principal(db, user)
    access_token = issue_token("at")
    refresh_token = issue_token("rt")
    session = SessionModel(
        id=new_id("ses"),
        user_id=user.id,
        access_token_hash=token_hash(access_token),
        refresh_token_hash=token_hash(refresh_token),
        expires_at=now_utc() + timedelta(seconds=settings.access_token_ttl_seconds),
        refresh_expires_at=now_utc() + timedelta(days=7),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    user.identity_source = provider
    user.sso_subject = user.sso_subject or external_subject
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now_utc()
    db.add(session)
    db.add(LoginLog(id=new_id("log"), username=user.username, user_id=user.id, login_type="sso", result="success"))
    audit(db, user.id, "auth", "sso_login", "user", user.id, after={"provider": provider, "subject": external_subject})
    db.commit()
    return success(
        {
            "accessToken": access_token,
            "tokenType": "Bearer",
            "expiresIn": settings.access_token_ttl_seconds,
            "refreshToken": refresh_token,
            "provider": provider,
            "subject": external_subject,
            "user": user_dto(db, user),
            "roles": principal.roles,
            "permissions": principal.permissions,
            "dataScope": principal.data_scope,
        },
        request.state.request_id,
    )


@router.post("/auth/sso/logout")
def sso_logout(db: Db, request: Request, authorization: Annotated[str | None, Header()] = None):
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        session = db.execute(select(SessionModel).where(SessionModel.access_token_hash == token_hash(token))).scalar_one_or_none()
        if session:
            session.revoked_at = now_utc()
            audit(db, session.user_id, "auth", "sso_logout", "session", session.id)
            db.commit()
    return success({}, request.state.request_id)


@router.get("/sso/providers")
def list_sso_providers(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("security:manage"))]):
    rows = db.execute(select(SsoProvider).order_by(SsoProvider.created_at.desc())).scalars().all()
    return success([sso_provider_dto(row) for row in rows], request.state.request_id)


@router.post("/sso/providers")
def create_sso_provider(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("security:manage"))], payload: dict[str, Any] = Body(...)):
    provider = SsoProvider(id=new_id("sso"), provider=payload["provider"], protocol=payload.get("protocol", "oidc"), status=payload.get("status", "enabled"), config=payload.get("config", {}), jit_enabled=payload.get("jitEnabled", False))
    db.add(provider)
    audit(db, auth.user.id, "sso", "create_provider", "sso_provider", provider.id, after=sso_provider_dto(provider))
    db.commit()
    return success(sso_provider_dto(provider), request.state.request_id)


@router.put("/sso/providers/{provider_id}")
def update_sso_provider(provider_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("security:manage"))], payload: dict[str, Any] = Body(...)):
    provider = db.get(SsoProvider, provider_id)
    if not provider:
        raise BusinessError(400001, "invalid request", 404)
    before = sso_provider_dto(provider)
    provider.protocol = payload.get("protocol", provider.protocol)
    provider.status = payload.get("status", provider.status)
    provider.config = payload.get("config", provider.config)
    provider.jit_enabled = payload.get("jitEnabled", provider.jit_enabled)
    provider.updated_at = now_utc()
    audit(db, auth.user.id, "sso", "update_provider", "sso_provider", provider.id, before=before, after=sso_provider_dto(provider))
    db.commit()
    return success(sso_provider_dto(provider), request.state.request_id)


@router.get("/me")
def me(auth: Auth, db: Db, request: Request):
    return success(user_dto(db, auth.user), request.state.request_id)


@router.get("/me/permissions")
def me_permissions(auth: Auth, request: Request):
    return success({"user": {"id": auth.user.id, "name": auth.user.name}, "roles": auth.roles, "permissions": auth.permissions, "dataScope": auth.data_scope}, request.state.request_id)


def user_dto(db: Session, user: User) -> dict[str, Any]:
    dep = db.get(Department, user.department_id) if user.department_id else None
    role_rows = db.execute(select(Role).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user.id)).scalars().all()
    position_rows = db.execute(select(Position).join(UserPosition, UserPosition.position_id == Position.id).where(UserPosition.user_id == user.id)).scalars().all()
    return {
        "id": user.id,
        "employeeNo": user.employee_no,
        "username": user.username,
        "name": user.name,
        "department": _brief(dep),
        "email": user.email,
        "mobile": user.mobile,
        "status": user.status,
        "seatStatus": user.seat_status,
        "identitySource": user.identity_source,
        "roles": [{"id": role.id, "name": role.name} for role in role_rows],
        "positions": [position_dto(position) for position in position_rows],
        "lastLoginAt": _iso(user.last_login_at),
        "passwordUpdatedAt": _iso(user.password_updated_at),
    }


def position_dto(position: Position) -> dict[str, Any]:
    return {"id": position.id, "name": position.name, "departmentId": position.department_id, "level": position.level, "status": position.status, "source": position.source, "createdAt": _iso(position.created_at)}


def sso_provider_dto(provider: SsoProvider) -> dict[str, Any]:
    safe_config = {k: ("***" if "secret" in k.lower() or "key" in k.lower() else v) for k, v in (provider.config or {}).items()}
    return {"id": provider.id, "provider": provider.provider, "protocol": provider.protocol, "status": provider.status, "config": safe_config, "jitEnabled": provider.jit_enabled, "createdAt": _iso(provider.created_at), "updatedAt": _iso(provider.updated_at)}


def apply_agent_data_scope(stmt, principal: Principal):
    scope = principal.data_scope or {"type": "self", "departmentIds": []}
    scope_type = scope.get("type", "self")
    if scope_type == "all":
        return stmt
    if scope_type in {"department", "departments"}:
        department_ids = scope.get("departmentIds") or ([principal.user.department_id] if principal.user.department_id else [])
        return stmt.where(Agent.department_id.in_(department_ids or [""]))
    return stmt.where(Agent.owner_id == principal.user.id)


def scoped_agent(db: Session, principal: Principal, agent_id: str) -> Agent | None:
    stmt = apply_agent_data_scope(select(Agent).where(Agent.id == agent_id, Agent.deleted_at.is_(None)), principal)
    return db.execute(stmt).scalar_one_or_none()


@router.get("/agents")
def list_agents(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("agent:view"))], keyword: str | None = None, status: str | None = None, departmentId: str | None = None, ownerId: str | None = None, modelId: str | None = None, page: int = 1, pageSize: int = 20):
    stmt = apply_agent_data_scope(select(Agent).where(Agent.deleted_at.is_(None)), auth)
    if keyword:
        stmt = stmt.where(Agent.name.like(f"%{keyword}%"))
    if status:
        stmt = stmt.where(Agent.status == status)
    if departmentId:
        stmt = stmt.where(Agent.department_id == departmentId)
    if ownerId:
        stmt = stmt.where(Agent.owner_id == ownerId)
    if modelId:
        stmt = stmt.where((Agent.primary_model_id == modelId) | (Agent.backup_model_id == modelId))
    items = [camel_agent(agent, db) for agent in db.execute(stmt.order_by(Agent.created_at.desc())).scalars().all()]
    return success(paginate(items, page, pageSize), request.state.request_id)


@router.post("/agents")
def create_agent(payload: AgentCreateRequest, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("agent:create"))]):
    pkg = db.execute(
        select(SeatPackage)
        .where(SeatPackage.status == "active", SeatPackage.total_count > SeatPackage.used_count)
        .order_by(SeatPackage.created_at.asc())
    ).scalars().first()
    if not pkg or pkg.total_count - pkg.used_count < 1:
        raise BusinessError(QUOTA_EXCEEDED, "quota exceeded", 422, {"required": 1, "available": max(pkg.total_count - pkg.used_count, 0) if pkg else 0, "seatPackageId": pkg.id if pkg else None})
    primary_model = db.get(LlmModel, payload.primaryModelId)
    if not primary_model or primary_model.status != "enabled":
        raise BusinessError(400001, "invalid request", 422, {"field": "primaryModelId", "reason": "model_not_enabled"})
    if payload.backupModelId:
        backup_model = db.get(LlmModel, payload.backupModelId)
        if not backup_model or backup_model.status != "enabled":
            raise BusinessError(400001, "invalid request", 422, {"field": "backupModelId", "reason": "model_not_enabled"})
    channels: list[MessageChannel] = []
    for channel_id in payload.messageChannelIds:
        channel = db.get(MessageChannel, channel_id)
        if not channel or channel.status != "enabled":
            raise BusinessError(400001, "invalid request", 422, {"field": "messageChannelIds", "channelId": channel_id, "reason": "channel_not_enabled"})
        channels.append(channel)
    if (payload.resourceSpec or {}).get("_mockBridgeFailure"):
        audit(
            db,
            auth.user.id,
            "agent",
            "create_failed",
            "agent",
            None,
            result="failed",
            error="bridge unavailable",
            after={"name": payload.name, "phase": "bridge_token", "deployTaskCreated": False},
        )
        db.commit()
        raise BusinessError(CLAW_PROXY_TIMEOUT, "bridge unavailable", 502, {"phase": "bridge_token", "deployTaskCreated": False})
    agent = Agent(
        id=new_id("agt_db"),
        bot_id=new_bot_id(),
        bridge_token_ref=new_id("bridge"),
        name=payload.name,
        type=payload.type,
        status="deploying",
        description=payload.description,
        department_id=payload.departmentId,
        owner_id=payload.ownerId,
        primary_model_id=payload.primaryModelId,
        backup_model_id=payload.backupModelId,
        resource_spec=payload.resourceSpec or {"cpu": 2, "memory": "4Gi", "storage": "20Gi", "gpu": 0},
        concurrency_limit=payload.concurrencyLimit,
        daily_call_limit=payload.dailyCallLimit,
        timeout_ms=payload.timeoutMs,
        memory_policy=payload.memoryPolicy,
    )
    db.add(agent)
    db.flush()
    db.add(AgentRuntimeSnapshot(agent_id=agent.id, cpu=agent.resource_spec.get("cpu", 2), memory=agent.resource_spec.get("memory", "4Gi"), storage=agent.resource_spec.get("storage", "20Gi"), gpu=agent.resource_spec.get("gpu", 0)))
    for sid in payload.skillIds:
        skill = db.get(Skill, sid)
        if not skill or skill.status != "enabled":
            raise BusinessError(400001, "invalid request", 422, {"field": "skillIds", "skillId": sid, "reason": "skill_not_enabled"})
        if not user_can_use_skill(db, auth, skill, agent.id):
            deny_business_permission(db, auth, "skill:install", {"skillId": sid})
        db.add(AgentBindSkill(agent_id=agent.id, skill_id=sid, package_name=skill.package_name, installed_version=skill.version, status="pending"))
    for kid in payload.knowledgeBaseIds:
        kb = db.get(KnowledgeBase, kid)
        if not kb or kb.status != "enabled":
            raise BusinessError(400001, "invalid request", 422, {"field": "knowledgeBaseIds", "knowledgeBaseId": kid})
        if not user_can_access_knowledge(db, auth, kb, agent_id=agent.id):
            deny_business_permission(db, auth, "knowledge:bind", {"knowledgeBaseId": kid})
        db.add(AgentBindKnowledge(agent_id=agent.id, knowledge_base_id=kid, scope="read"))
    for channel in channels:
        bind = ChannelBindAgent(id=new_id("cba"), channel_id=channel.id, agent_id=agent.id, status="active", created_by=auth.user.id)
        db.add(bind)
        channel_audit(db, auth.user.id, "bind_agent_on_create", channel.id, detail={"agentId": agent.id})
    pkg.used_count += 1
    db.add(
        SeatAssignment(
            id=new_id("seat_asg"),
            seat_package_id=pkg.id,
            assignee_type="agent",
            assignee_id=agent.id,
            agent_id=agent.id,
            status="active",
        )
    )
    task = task_for_agent(db, agent, "deploy", "queued")
    audit(db, auth.user.id, "agent", "create", "agent", agent.id)
    db.commit()
    return success({"id": agent.id, "botId": agent.bot_id, "status": agent.status, "deployTaskId": task.id}, request.state.request_id)


def release_agent_resources(db: Session, agent: Agent, actor_id: str | None, reason: str) -> dict[str, Any]:
    released: dict[str, Any] = {"reclaimedSeats": [], "disabledChannelBindings": [], "disabledBusinessSystemGrants": [], "revokedShareGrants": []}
    seats = db.execute(
        select(SeatAssignment).where(
            SeatAssignment.assignee_type == "agent",
            SeatAssignment.agent_id == agent.id,
            SeatAssignment.status == "active",
        )
    ).scalars().all()
    for seat in seats:
        before = seat_assignment_dto(seat)
        pkg = db.get(SeatPackage, seat.seat_package_id)
        if pkg and pkg.used_count > 0:
            pkg.used_count -= 1
        seat.status = "reclaimed"
        after = seat_assignment_dto(seat)
        released["reclaimedSeats"].append(after)
        record_seat_event(db, "reclaim", seat, actor_id, before=before, after=after, reason=reason)
        audit(db, actor_id, "seat", "reclaim", "seat_assignment", seat.id, before=before, after=after | {"reason": reason, "agentId": agent.id})

    channel_binds = db.execute(
        select(ChannelBindAgent).where(ChannelBindAgent.agent_id == agent.id, ChannelBindAgent.status == "active")
    ).scalars().all()
    for bind in channel_binds:
        bind.status = "disabled"
        released["disabledChannelBindings"].append({"channelId": bind.channel_id, "agentId": agent.id})
        channel_audit(db, actor_id, "unbind_agent_on_archive", bind.channel_id, detail={"agentId": agent.id, "reason": reason})

    business_grants = db.execute(
        select(BusinessSystemAgentGrant).where(BusinessSystemAgentGrant.agent_id == agent.id, BusinessSystemAgentGrant.status == "active")
    ).scalars().all()
    for grant in business_grants:
        grant.status = "disabled"
        system = db.get(BusinessSystem, grant.business_system_id)
        if system and agent.id in (system.allowed_agent_ids or []):
            system.allowed_agent_ids = [item for item in (system.allowed_agent_ids or []) if item != agent.id]
        released["disabledBusinessSystemGrants"].append({"businessSystemId": grant.business_system_id, "agentId": agent.id})
        channel_audit(db, actor_id, "disable_agent_grant_on_archive", None, object_type="business_system", object_id=grant.business_system_id, module="business_system", detail={"agentId": agent.id, "reason": reason})

    share_grants = db.execute(select(ShareGrant).where(ShareGrant.agent_id == agent.id, ShareGrant.status == "active")).scalars().all()
    for grant in share_grants:
        before = share_dto(grant)
        reclaimed = reclaim_share_seats(db, grant, actor_id, reason)
        grant.status = "revoked"
        after = share_dto(grant) | {"reclaimedSeats": reclaimed}
        released["revokedShareGrants"].append({"id": grant.id, "scopeType": grant.scope_type, "scopeId": grant.scope_id})
        audit(db, actor_id, "share", "revoke_on_archive", "share_grant", grant.id, before=before, after=after)

    return released


@router.get("/agents/{agent_id}")
def get_agent(agent_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("agent:view"))]):
    agent = scoped_agent(db, auth, agent_id)
    if not agent:
        raise BusinessError(400001, "invalid request", 404)
    skills = db.execute(select(AgentBindSkill).where(AgentBindSkill.agent_id == agent_id)).scalars().all()
    kbs = db.execute(select(AgentBindKnowledge).where(AgentBindKnowledge.agent_id == agent_id)).scalars().all()
    tasks = db.execute(select(AgentDeployTask).where(AgentDeployTask.agent_id == agent_id).order_by(AgentDeployTask.created_at.desc()).limit(20)).scalars().all()
    alerts = db.execute(select(Alert).where(Alert.source_id == agent_id).order_by(Alert.created_at.desc()).limit(20)).scalars().all()
    versions = db.execute(select(AgentVersion).where(AgentVersion.agent_id == agent_id).order_by(AgentVersion.id.desc()).limit(20)).scalars().all()
    events = db.execute(select(AgentStateEvent).where(AgentStateEvent.agent_id == agent_id).order_by(AgentStateEvent.created_at.desc()).limit(20)).scalars().all()
    audit_rows = db.execute(select(AuditLog).where(AuditLog.object_id == agent_id).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(20)).scalars().all()
    integrity_by_id = audit_integrity_map(db)
    return success(
        {
            "basic": camel_agent(agent, db),
            "runtime": camel_agent(agent, db),
            "skills": [{"skillId": s.skill_id, "packageName": s.package_name, "installedVersion": s.installed_version, "status": s.status} for s in skills],
            "knowledgeBases": [{"knowledgeBaseId": k.knowledge_base_id, "scope": k.scope} for k in kbs],
            "deployHistory": [task_dto(t) for t in tasks],
            "versionHistory": [agent_version_dto(v) for v in versions],
            "stateEvents": [agent_state_event_dto(e) for e in events],
            "callStats": {"todayCallCount": 0, "avgLatencyMs": 0},
            "alerts": [alert_dto(a) for a in alerts],
            "auditLogs": [audit_log_dto(row, integrity_by_id) for row in audit_rows],
        },
        request.state.request_id,
    )


def task_dto(task: AgentDeployTask) -> dict[str, Any]:
    return {"id": task.id, "agentId": task.agent_id, "action": task.action, "status": task.status, "phase": task.phase, "progress": task.progress, "node": task.node, "startedAt": _iso(task.started_at), "endedAt": _iso(task.ended_at), "errorCode": task.error_code, "errorMessage": task.error_message, "retryAdvice": task.retry_advice}


def agent_version_dto(row: AgentVersion) -> dict[str, Any]:
    return {"id": row.id, "agentId": row.agent_id, "version": row.version, "configSnapshot": row.config_snapshot, "deployedAt": _iso(row.deployed_at), "rollbackFrom": row.rollback_from}


def agent_state_event_dto(row: AgentStateEvent) -> dict[str, Any]:
    return {"id": row.id, "agentId": row.agent_id, "fromStatus": row.from_status, "toStatus": row.to_status, "reason": row.reason, "operatorId": row.operator_id, "createdAt": _iso(row.created_at)}


def record_agent_task_failure_if_needed(db: Session, auth: Principal, task: AgentDeployTask) -> None:
    if task.status != "failed" or not task.error_code:
        return
    existing = db.execute(
        select(Alert).where(
            Alert.source_type == "agent",
            Alert.source_id == task.agent_id,
            Alert.error_code == task.error_code,
            Alert.category == "task_failure",
        )
    ).scalar_one_or_none()
    if not existing:
        agent = db.get(Agent, task.agent_id)
        db.add(
            Alert(
                id=new_id("alt"),
                level="P1",
                status="pending",
                source_type="agent",
                source_id=task.agent_id,
                category="task_failure",
                error_code=task.error_code,
                title=f"Agent {task.action} task failed",
                detail=task.error_message,
                root_cause="External Claw Proxy deployment call failed or timed out.",
                suggestion=task.retry_advice,
                owner_id=agent.owner_id if agent else None,
            )
        )
    audited = db.execute(
        select(AuditLog.id).where(
            AuditLog.module == "agent_task",
            AuditLog.action == "failed",
            AuditLog.object_id == task.id,
        )
    ).scalar_one_or_none()
    if not audited:
        audit(
            db,
            auth.user.id,
            "agent_task",
            "failed",
            "agent_deploy_task",
            task.id,
            result="failed",
            error=task.error_message,
            after=task_dto(task),
        )


@router.get("/agents/{agent_id}/versions")
def agent_versions(agent_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("agent:view"))], page: int = 1, pageSize: int = 20):
    if not scoped_agent(db, auth, agent_id):
        raise BusinessError(400001, "invalid request", 404)
    rows = db.execute(select(AgentVersion).where(AgentVersion.agent_id == agent_id).order_by(AgentVersion.id.desc())).scalars().all()
    return success(paginate([agent_version_dto(row) for row in rows], page, pageSize), request.state.request_id)


@router.get("/agents/{agent_id}/state-events")
def agent_state_events(agent_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("agent:view"))], page: int = 1, pageSize: int = 20):
    if not scoped_agent(db, auth, agent_id):
        raise BusinessError(400001, "invalid request", 404)
    rows = db.execute(select(AgentStateEvent).where(AgentStateEvent.agent_id == agent_id).order_by(AgentStateEvent.created_at.desc())).scalars().all()
    return success(paginate([agent_state_event_dto(row) for row in rows], page, pageSize), request.state.request_id)


@router.post("/agents/{agent_id}/rollback")
def rollback_agent(agent_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("agent:deploy"))], payload: dict[str, Any] = Body(...)):
    agent = scoped_agent(db, auth, agent_id)
    if not agent:
        raise BusinessError(400001, "invalid request", 404)
    target = db.execute(
        select(AgentVersion)
        .where(AgentVersion.agent_id == agent_id, AgentVersion.version == payload["version"])
        .order_by(AgentVersion.id.desc())
    ).scalars().first()
    if not target:
        raise BusinessError(400001, "invalid request", 404, {"field": "version"})
    current_version = agent.version
    snapshot = target.config_snapshot or {}
    previous_status = agent.status
    agent.name = snapshot.get("name", agent.name)
    agent.description = snapshot.get("description", agent.description)
    agent.version = target.version
    agent.primary_model_id = snapshot.get("primaryModelId", agent.primary_model_id)
    agent.backup_model_id = snapshot.get("backupModelId", agent.backup_model_id)
    agent.resource_spec = snapshot.get("resourceSpec", agent.resource_spec)
    agent.concurrency_limit = snapshot.get("concurrencyLimit", agent.concurrency_limit)
    agent.daily_call_limit = snapshot.get("dailyCallLimit", agent.daily_call_limit)
    agent.timeout_ms = snapshot.get("timeoutMs", agent.timeout_ms)
    agent.memory_policy = snapshot.get("memoryPolicy", agent.memory_policy)
    agent.status = "running" if previous_status in {"running", "upgrading", "abnormal"} else previous_status
    add_agent_version(db, agent, agent.version, rollback_from=current_version)
    add_agent_state_event(db, agent, previous_status, agent.status, auth.user.id, payload.get("reason") or f"rollback_to_{target.version}")
    task = task_for_agent(db, agent, "rollback", "queued")
    audit(db, auth.user.id, "agent", "rollback", "agent", agent_id, before={"version": current_version}, after={"version": agent.version, "rollbackFrom": current_version})
    db.commit()
    return success({"taskId": task.id, "status": "queued", "version": agent.version, "rollbackFrom": current_version}, request.state.request_id)


@router.post("/agents/{agent_id}/deploy")
@router.post("/agents/{agent_id}/start")
@router.post("/agents/{agent_id}/stop")
@router.post("/agents/{agent_id}/restart")
@router.post("/agents/{agent_id}/upgrade")
@router.post("/agents/{agent_id}/archive")
@router.post("/agents/{agent_id}/violation-offline")
def lifecycle(agent_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("agent:deploy"))], payload: dict[str, Any] = Body(default_factory=dict)):
    action = request.url.path.rsplit("/", 1)[-1]
    agent = scoped_agent(db, auth, agent_id)
    if not agent:
        raise BusinessError(400001, "invalid request", 404)
    allowed = {
        "deploy": {"draft", "stopped", "abnormal", "deploying"},
        "start": {"draft", "stopped", "abnormal"},
        "stop": {"running", "abnormal", "deploying"},
        "restart": {"running", "abnormal"},
        "upgrade": {"running", "stopped"},
        "archive": {"stopped", "draft", "abnormal"},
        "violation-offline": {"running", "abnormal"},
    }
    if agent.status not in allowed[action]:
        raise BusinessError(INVALID_STATE, "invalid state", 409)
    target = {"stop": "stopping", "restart": "running", "upgrade": "upgrading", "archive": "archived", "violation-offline": "violation_offline"}.get(action, "deploying")
    previous_status = agent.status
    previous_version = agent.version
    if action == "upgrade":
        add_agent_version(db, agent, previous_version)
        agent.version = payload.get("targetVersion") or next_agent_version(agent.version)
    approval_id = None
    evidence = None
    if action == "violation-offline":
        evidence = {
            "agentId": agent.id,
            "previousStatus": previous_status,
            "targetStatus": target,
            "reason": payload.get("reason") or "violation_offline",
            "evidence": payload.get("evidence") or payload.get("evidenceLinks") or [],
            "riskLevel": "critical",
        }
        approval = ApprovalRequest(
            id=new_id("apr"),
            type="violation_offline",
            risk_level="critical",
            applicant_id=auth.user.id,
            status="approved",
            reason=evidence["reason"],
            payload_snapshot=evidence,
        )
        db.add(approval)
        db.flush()
        step = ensure_approval_step(db, approval, auth.user.id)
        step.approver_id = auth.user.id
        step.decision = "approved"
        step.comment = payload.get("comment") or "emergency violation offline"
        step.decided_at = now_utc()
        approval_id = approval.id
    agent.status = target
    released = release_agent_resources(db, agent, auth.user.id, "agent archived") if action == "archive" else None
    add_agent_state_event(db, agent, previous_status, target, auth.user.id, payload.get("reason") or action)
    task = task_for_agent(db, agent, action, "queued")
    audit(db, auth.user.id, "agent", action, "agent", agent_id, before={"status": previous_status}, after={"status": target, "approvalId": approval_id, "evidence": evidence, "releasedResources": released})
    db.commit()
    return success({"taskId": task.id, "status": "queued", "targetVersion": agent.version if action == "upgrade" else None, "approvalId": approval_id, "evidence": evidence, "releasedResources": released}, request.state.request_id)


@router.delete("/agents/{agent_id}")
def delete_agent(agent_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("agent:delete"))]):
    agent = scoped_agent(db, auth, agent_id)
    if not agent:
        raise BusinessError(400001, "invalid request", 404)
    if agent.status not in {"draft", "stopped", "archived"}:
        raise BusinessError(INVALID_STATE, "invalid state", 409)
    released = release_agent_resources(db, agent, auth.user.id, "agent deleted")
    agent.deleted_at = now_utc()
    audit(db, auth.user.id, "agent", "delete", "agent", agent_id, after={"releasedResources": released})
    db.commit()
    return success({"releasedResources": released}, request.state.request_id)


@router.put("/agents/{agent_id}/model")
def switch_model(agent_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("model:manage"))], payload: dict[str, Any] = Body(...)):
    agent = scoped_agent(db, auth, agent_id)
    if not agent:
        raise BusinessError(400001, "invalid request", 404)
    agent.primary_model_id = payload.get("primaryModelId")
    agent.backup_model_id = payload.get("backupModelId")
    audit(db, auth.user.id, "model", "switch", "agent", agent_id)
    db.commit()
    return success(camel_agent(agent, db), request.state.request_id)


@router.get("/agent-tasks/{task_id}")
def get_task(task_id: str, db: Db, request: Request, auth: Auth):
    task = db.get(AgentDeployTask, task_id)
    if not task:
        raise BusinessError(400001, "invalid request", 404)
    previous_task_status = task.status
    agent = db.get(Agent, task.agent_id)
    previous_agent_status = agent.status if agent else None
    process_agent_task_if_mock(db, task)
    if agent and previous_task_status in {"queued", "running"} and task.status == "success":
        add_agent_state_event(db, agent, previous_agent_status, agent.status, auth.user.id, f"{task.action}_completed")
        if task.action in {"deploy", "upgrade"}:
            exists = db.execute(select(AgentVersion).where(AgentVersion.agent_id == agent.id, AgentVersion.version == agent.version).order_by(AgentVersion.id.desc())).scalars().first()
            if not exists or exists.rollback_from:
                add_agent_version(db, agent, agent.version)
    record_agent_task_failure_if_needed(db, auth, task)
    db.commit()
    return success(task_dto(task), request.state.request_id)


@router.post("/agents/{agent_id}/sync")
def sync_agent(agent_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("agent:ops"))]):
    agent = scoped_agent(db, auth, agent_id)
    if not agent:
        raise BusinessError(400001, "invalid request", 404)
    runtime = db.execute(select(AgentRuntimeSnapshot).where(AgentRuntimeSnapshot.agent_id == agent_id)).scalar_one_or_none()
    if not runtime:
        raise BusinessError(400001, "invalid request", 404)
    before = {"lastSyncAt": _iso(runtime.last_sync_at), "syncError": runtime.sync_error}
    runtime.last_sync_at = now_utc()
    runtime.sync_error = None
    audit(db, auth.user.id, "runtime_sync", "manual_sync", "agent", agent_id, before=before, after={"lastSyncAt": _iso(runtime.last_sync_at), "syncError": runtime.sync_error})
    db.commit()
    return success({"status": agent.status, "lastSyncAt": _iso(runtime.last_sync_at), "syncError": runtime.sync_error}, request.state.request_id)


def resolve_runtime_sync_targets(db: Session, principal: Principal, payload: dict[str, Any]) -> list[str]:
    scope_type = payload.get("scopeType", "all")
    if scope_type == "selected":
        requested = list(dict.fromkeys(payload.get("targetIds") or []))
        if not requested:
            return []
        visible = set(db.execute(apply_agent_data_scope(select(Agent.id).where(Agent.deleted_at.is_(None), Agent.id.in_(requested)), principal)).scalars().all())
        unauthorized = [target_id for target_id in requested if target_id not in visible]
        if unauthorized:
            raise BusinessError(FORBIDDEN, "forbidden", 403, {"unauthorizedTargetIds": unauthorized})
        return requested
    filters = payload.get("filters") or {}
    stmt = apply_agent_data_scope(select(Agent).where(Agent.deleted_at.is_(None)), principal)
    if status := filters.get("status"):
        stmt = stmt.where(Agent.status == status)
    if department_id := filters.get("departmentId"):
        stmt = stmt.where(Agent.department_id == department_id)
    if owner_id := filters.get("ownerId"):
        stmt = stmt.where(Agent.owner_id == owner_id)
    return [agent.id for agent in db.execute(stmt.order_by(Agent.created_at.desc())).scalars().all()]


def runtime_sync_job_dto(job: RuntimeSyncJob) -> dict[str, Any]:
    success_count = job.success_count or 0
    failed_count = job.failed_count or 0
    total = job.total or 0
    progress = int(((success_count + failed_count) / total) * 100) if total else 0
    return {
        "id": job.id,
        "scopeType": job.scope_type,
        "scopeSnapshot": job.scope_snapshot,
        "status": job.status,
        "total": total,
        "successCount": success_count,
        "failedCount": failed_count,
        "progress": progress,
        "errorMessage": job.error_message,
        "operator": {"id": job.operator_id},
        "startedAt": _iso(job.started_at),
        "endedAt": _iso(job.ended_at),
        "createdAt": _iso(job.created_at),
    }


def process_runtime_sync_job_if_mock(db: Session, job: RuntimeSyncJob) -> None:
    if job.status not in {"queued", "running"}:
        return
    job.status = "running"
    job.started_at = job.started_at or now_utc()
    snapshot = job.scope_snapshot or {}
    metrics = snapshot.get("metrics") or {}
    fail_ids = set(snapshot.get("failAgentIds") or [])
    success_count = failed_count = 0
    for agent_id in snapshot.get("targetIds") or []:
        runtime = db.execute(select(AgentRuntimeSnapshot).where(AgentRuntimeSnapshot.agent_id == agent_id)).scalar_one_or_none()
        if not runtime:
            failed_count += 1
            continue
        if agent_id in fail_ids:
            runtime.sync_error = "runtime sync failed"
            runtime.last_sync_at = now_utc()
            failed_count += 1
            continue
        runtime.container_count = int(metrics.get("containerCount", runtime.container_count))
        runtime.qps = float(metrics.get("qps", runtime.qps))
        runtime.latency_ms = int(metrics.get("latencyMs", runtime.latency_ms))
        runtime.current_users = int(metrics.get("currentUsers", runtime.current_users))
        runtime.max_users = int(metrics.get("maxUsers", runtime.max_users))
        runtime.last_sync_at = now_utc()
        runtime.sync_error = None
        success_count += 1
    job.success_count = success_count
    job.failed_count = failed_count
    job.status = "success" if failed_count == 0 else "partial_success"
    job.error_message = None if failed_count == 0 else f"{failed_count} agent(s) sync failed"
    job.ended_at = now_utc()


@router.post("/sync-jobs")
def create_runtime_sync_job(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("agent:ops"))], payload: dict[str, Any] = Body(default_factory=dict)):
    target_ids = resolve_runtime_sync_targets(db, auth, payload)
    snapshot = {
        "targetIds": target_ids,
        "filters": payload.get("filters") or {},
        "metrics": payload.get("metrics") or {},
        "failAgentIds": payload.get("failAgentIds") or [],
    }
    job = RuntimeSyncJob(id=new_id("sync"), scope_type=payload.get("scopeType", "all"), scope_snapshot=snapshot, status="queued", total=len(target_ids), success_count=0, failed_count=0, operator_id=auth.user.id)
    db.add(job)
    audit(db, auth.user.id, "runtime_sync", "create", "sync_job", job.id, after=runtime_sync_job_dto(job))
    db.commit()
    return success(runtime_sync_job_dto(job), request.state.request_id)


@router.get("/sync-jobs")
def runtime_sync_jobs(db: Db, request: Request, auth: Auth, page: int = 1, pageSize: int = 20, status: str | None = None):
    stmt = select(RuntimeSyncJob)
    if status:
        stmt = stmt.where(RuntimeSyncJob.status == status)
    rows = db.execute(stmt.order_by(RuntimeSyncJob.created_at.desc())).scalars().all()
    return success(paginate([runtime_sync_job_dto(job) for job in rows], page, pageSize), request.state.request_id)


@router.get("/sync-jobs/{job_id}")
def runtime_sync_job_detail(job_id: str, db: Db, request: Request, auth: Auth):
    job = db.get(RuntimeSyncJob, job_id)
    if not job:
        raise BusinessError(400001, "invalid request", 404)
    process_runtime_sync_job_if_mock(db, job)
    if job.status in {"success", "partial_success"}:
        audit(db, auth.user.id, "runtime_sync", job.status, "sync_job", job.id, after=runtime_sync_job_dto(job))
    db.commit()
    return success(runtime_sync_job_dto(job), request.state.request_id)


@router.get("/agents/{agent_id}/logs")
def agent_logs(
    agent_id: str,
    db: Db,
    request: Request,
    auth: Annotated[Principal, Depends(require_permission("agent:view"))],
    logType: str | None = "runtime",
    level: str | None = None,
    keyword: str | None = None,
    startTime: str | None = None,
    endTime: str | None = None,
    page: int = 1,
    pageSize: int = 50,
):
    if not scoped_agent(db, auth, agent_id):
        raise BusinessError(400001, "invalid request", 404)
    stmt = select(AgentLogIndex).where(AgentLogIndex.agent_id == agent_id)
    if logType:
        stmt = stmt.where(AgentLogIndex.log_type == logType)
    if level:
        stmt = stmt.where(AgentLogIndex.level == level)
    if keyword:
        stmt = stmt.where(AgentLogIndex.message.like(f"%{keyword}%"))
    if startTime:
        stmt = stmt.where(AgentLogIndex.created_at >= datetime.fromisoformat(startTime.replace("Z", "+00:00")))
    if endTime:
        stmt = stmt.where(AgentLogIndex.created_at <= datetime.fromisoformat(endTime.replace("Z", "+00:00")))
    rows = db.execute(stmt.order_by(AgentLogIndex.created_at.desc())).scalars().all()
    return success(
        paginate(
            [
                {
                    "id": row.id,
                    "agentId": row.agent_id,
                    "logType": row.log_type,
                    "level": row.level,
                    "message": row.message,
                    "traceId": row.trace_id,
                    "source": row.source,
                    "createdAt": _iso(row.created_at),
                }
                for row in rows
            ],
            page,
            pageSize,
        ),
        request.state.request_id,
    )


@router.post("/dev/agent-logs")
def dev_agent_log(db: Db, request: Request, payload: dict[str, Any] = Body(...)):
    agent_id = payload.get("agentId")
    if not agent_id or not db.get(Agent, agent_id):
        raise BusinessError(400001, "invalid request", 404, {"field": "agentId"})
    row = AgentLogIndex(
        id=new_id("log"),
        agent_id=agent_id,
        log_type=payload.get("logType", "runtime"),
        level=payload.get("level", "info"),
        message=payload.get("message", ""),
        trace_id=payload.get("traceId"),
        source=payload.get("source", "dev"),
    )
    db.add(row)
    db.commit()
    return success({"id": row.id}, request.state.request_id)


def runtime_config_payload(agent: Agent) -> dict[str, Any]:
    return {
        "concurrencyLimit": agent.concurrency_limit,
        "dailyCallLimit": agent.daily_call_limit,
        "timeoutMs": agent.timeout_ms,
        "resourceSpec": agent.resource_spec,
        "memoryPolicy": agent.memory_policy,
        "primaryModelId": agent.primary_model_id,
        "backupModelId": agent.backup_model_id,
    }


def runtime_config_dto(row: AgentRuntimeConfig) -> dict[str, Any]:
    return {
        "id": row.id,
        "agentId": row.agent_id,
        "version": row.version,
        "config": row.config,
        "restartRequired": row.restart_required,
        "restartTaskId": row.restart_task_id,
        "operatorId": row.operator_id,
        "createdAt": _iso(row.created_at),
    }


@router.get("/agents/{agent_id}/runtime-config")
def get_runtime_config(agent_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("agent:view"))], page: int = 1, pageSize: int = 20):
    agent = scoped_agent(db, auth, agent_id)
    if not agent:
        raise BusinessError(400001, "invalid request", 404)
    rows = db.execute(select(AgentRuntimeConfig).where(AgentRuntimeConfig.agent_id == agent_id).order_by(AgentRuntimeConfig.version.desc())).scalars().all()
    latest = rows[0] if rows else None
    return success(
        {
            "agentId": agent_id,
            "current": latest.config if latest else runtime_config_payload(agent),
            "configVersion": latest.version if latest else 0,
            "restartTaskId": latest.restart_task_id if latest else None,
            "history": paginate([runtime_config_dto(row) for row in rows], page, pageSize),
        },
        request.state.request_id,
    )


@router.put("/agents/{agent_id}/runtime-config")
def runtime_config(agent_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("agent:ops"))], payload: dict[str, Any] = Body(...)):
    agent = scoped_agent(db, auth, agent_id)
    if not agent:
        raise BusinessError(400001, "invalid request", 404)
    before = runtime_config_payload(agent)
    agent.concurrency_limit = payload.get("concurrencyLimit", agent.concurrency_limit)
    agent.daily_call_limit = payload.get("dailyCallLimit", agent.daily_call_limit)
    agent.timeout_ms = payload.get("timeoutMs", agent.timeout_ms)
    agent.resource_spec = payload.get("resourceSpec", agent.resource_spec)
    agent.memory_policy = payload.get("memoryPolicy", agent.memory_policy)
    if payload.get("primaryModelId") is not None:
        agent.primary_model_id = payload.get("primaryModelId")
    if payload.get("backupModelId") is not None:
        agent.backup_model_id = payload.get("backupModelId")
    latest_version = db.execute(select(func.max(AgentRuntimeConfig.version)).where(AgentRuntimeConfig.agent_id == agent_id)).scalar() or 0
    restart_required = bool(payload.get("restartAfterUpdated"))
    restart_task_id = None
    if restart_required:
        restart_task_id = task_for_agent(db, agent, "restart", "queued").id
    row = AgentRuntimeConfig(
        id=new_id("arc"),
        agent_id=agent_id,
        version=latest_version + 1,
        config=runtime_config_payload(agent),
        restart_required=restart_required,
        restart_task_id=restart_task_id,
        operator_id=auth.user.id,
    )
    db.add(row)
    audit(db, auth.user.id, "agent", "runtime_config", "agent", agent_id, before=before, after=row.config)
    db.commit()
    data = camel_agent(agent, db)
    data["configVersion"] = row.version
    data["restartTaskId"] = restart_task_id
    data["runtimeConfig"] = runtime_config_dto(row)
    return success(data, request.state.request_id)


def resolve_batch_targets(db: Session, principal: Principal, payload: dict[str, Any]) -> list[str]:
    scope_type = payload.get("scopeType", "selected")
    requested = list(dict.fromkeys(payload.get("targetIds") or []))
    if scope_type == "selected":
        if not requested:
            return []
        visible = set(
            db.execute(
                apply_agent_data_scope(select(Agent.id).where(Agent.deleted_at.is_(None), Agent.id.in_(requested)), principal)
            ).scalars().all()
        )
        unauthorized = [target_id for target_id in requested if target_id not in visible]
        if unauthorized:
            raise BusinessError(FORBIDDEN, "forbidden", 403, {"unauthorizedTargetIds": unauthorized})
        return requested

    filters = payload.get("filters") or {}
    stmt = apply_agent_data_scope(select(Agent).where(Agent.deleted_at.is_(None)), principal)
    if keyword := filters.get("keyword"):
        stmt = stmt.where(Agent.name.like(f"%{keyword}%"))
    if status := filters.get("status"):
        stmt = stmt.where(Agent.status == status)
    if department_id := filters.get("departmentId"):
        stmt = stmt.where(Agent.department_id == department_id)
    if owner_id := filters.get("ownerId"):
        stmt = stmt.where(Agent.owner_id == owner_id)
    if model_id := filters.get("modelId"):
        stmt = stmt.where((Agent.primary_model_id == model_id) | (Agent.backup_model_id == model_id))
    return [agent.id for agent in db.execute(stmt.order_by(Agent.created_at.desc())).scalars().all()]


@router.post("/batch-tasks")
def create_batch(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("agent:batch"))], payload: dict[str, Any] = Body(...)):
    targets = resolve_batch_targets(db, auth, payload)
    high_risk_types = {"delete", "archive", "violation_offline", "violation-offline"}
    is_high_risk = payload["type"] in high_risk_types
    approval_id = None
    batch_type = payload["type"]
    status = "pending_approval" if is_high_risk and not payload.get("approvalId") else "queued"
    if status == "pending_approval":
        approval = ApprovalRequest(
            id=new_id("apr"),
            type=f"batch_{batch_type}_agent",
            risk_level="high",
            applicant_id=auth.user.id,
            status="pending",
            reason=payload.get("reason"),
            payload_snapshot={"targetIds": targets, "batchType": batch_type},
        )
        db.add(approval)
        db.flush()
        ensure_approval_step(db, approval)
        approval_id = approval.id
    else:
        approval_id = payload.get("approvalId")
        if is_high_risk and approval_id:
            approval = db.get(ApprovalRequest, approval_id)
            expected_type = f"batch_{batch_type}_agent"
            if not approval or approval.type != expected_type:
                raise BusinessError(400001, "invalid request", 404, {"field": "approvalId"})
            if approval.status != "approved":
                raise BusinessError(APPROVAL_REQUIRED, "approval required", 409, {"approvalId": approval.id, "status": approval.status})
            snapshot = approval.payload_snapshot or {}
            batch_type = snapshot.get("batchType") or batch_type
            targets = resolve_batch_targets(db, auth, {"scopeType": "selected", "targetIds": snapshot.get("targetIds") or []})
    batch = BatchTask(id=new_id("bat"), type=batch_type, scope_type=payload.get("scopeType", "selected"), scope_snapshot={"targetIds": targets, "filters": payload.get("filters") or {}}, total=len(targets), status=status, operator_id=auth.user.id, approval_id=approval_id, strategy=payload.get("strategy", {}), reason=payload.get("reason"))
    db.add(batch)
    for target in targets:
        db.add(BatchTaskItem(id=new_id("bti"), batch_task_id=batch.id, target_id=target, action=batch.type, status="queued"))
    audit(db, auth.user.id, "batch", "create", "batch_task", batch.id)
    db.commit()
    return success(batch_dto(batch, db), request.state.request_id)


def batch_dto(batch: BatchTask, db: Session) -> dict[str, Any]:
    progress = int(((batch.success_count + batch.failed_count + batch.skipped_count) / batch.total) * 100) if batch.total else 0
    operator = db.get(User, batch.operator_id) if batch.operator_id else None
    return {"id": batch.id, "type": batch.type, "status": batch.status, "total": batch.total, "successCount": batch.success_count, "failedCount": batch.failed_count, "skippedCount": batch.skipped_count, "progress": progress, "operator": {"id": batch.operator_id, "name": operator.name if operator else None}, "approvalId": batch.approval_id, "strategy": batch.strategy, "createdAt": _iso(batch.created_at)}


@router.get("/batch-tasks/{batch_id}")
def get_batch(batch_id: str, db: Db, request: Request, auth: Auth):
    batch = db.get(BatchTask, batch_id)
    if not batch:
        raise BusinessError(400001, "invalid request", 404)
    process_batch_if_mock(db, batch)
    db.commit()
    return success(batch_dto(batch, db), request.state.request_id)


@router.get("/batch-tasks/{batch_id}/items")
def get_batch_items(batch_id: str, db: Db, request: Request, auth: Auth, page: int = 1, pageSize: int = 50):
    if not db.get(BatchTask, batch_id):
        raise BusinessError(400001, "invalid request", 404, {"field": "batchId"})
    items = db.execute(select(BatchTaskItem).where(BatchTaskItem.batch_task_id == batch_id)).scalars().all()
    data = [{"id": i.id, "targetId": i.target_id, "action": i.action, "status": i.status, "startedAt": _iso(i.started_at), "endedAt": _iso(i.ended_at), "errorCode": i.error_code, "errorMessage": i.error_message} for i in items]
    return success(paginate(data, page, pageSize), request.state.request_id)


@router.get("/batch-tasks/{batch_id}/export")
def export_batch(batch_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("agent:batch"))]):
    if not db.get(BatchTask, batch_id):
        raise BusinessError(400001, "invalid request", 404, {"field": "batchId"})
    task = create_export_task(db, auth, "batch", {"batchTaskId": batch_id})
    db.commit()
    return success({"taskId": task.id, "status": task.status, "downloadUrl": task.file_url, "watermark": task.watermark}, request.state.request_id)


@router.get("/org/departments/tree")
def departments_tree(db: Db, request: Request, auth: Auth):
    deps = db.execute(select(Department)).scalars().all()
    return success([{"id": d.id, "parentId": d.parent_id, "name": d.name, "leaderId": d.leader_id, "status": d.status, "source": d.source} for d in deps], request.state.request_id)


@router.get("/org/positions")
def positions(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("security:manage"))], departmentId: str | None = None, status: str | None = None, page: int = 1, pageSize: int = 20):
    stmt = select(Position)
    if departmentId:
        stmt = stmt.where(Position.department_id == departmentId)
    if status:
        stmt = stmt.where(Position.status == status)
    rows = db.execute(stmt.order_by(Position.created_at.desc())).scalars().all()
    return success(paginate([position_dto(row) for row in rows], page, pageSize), request.state.request_id)


@router.post("/org/positions")
def create_position(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("security:manage"))], payload: dict[str, Any] = Body(...)):
    row = Position(id=payload.get("id") or new_id("pos"), name=payload["name"], department_id=payload.get("departmentId"), level=payload.get("level"), status=payload.get("status", "active"), source=payload.get("source", "local"))
    db.add(row)
    audit(db, auth.user.id, "org", "create_position", "position", row.id, after=position_dto(row))
    db.commit()
    return success(position_dto(row), request.state.request_id)


@router.put("/org/positions/{position_id}")
def update_position(position_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("security:manage"))], payload: dict[str, Any] = Body(...)):
    row = db.get(Position, position_id)
    if not row:
        raise BusinessError(400001, "invalid request", 404)
    before = position_dto(row)
    row.name = payload.get("name", row.name)
    row.department_id = payload.get("departmentId", row.department_id)
    row.level = payload.get("level", row.level)
    row.status = payload.get("status", row.status)
    audit(db, auth.user.id, "org", "update_position", "position", row.id, before=before, after=position_dto(row))
    db.commit()
    return success(position_dto(row), request.state.request_id)


@router.get("/org/users")
def users(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("security:manage"))], page: int = 1, pageSize: int = 20, keyword: str | None = None, departmentId: str | None = None, status: str | None = None, seatStatus: str | None = None):
    stmt = select(User)
    if keyword:
        stmt = stmt.where(User.name.like(f"%{keyword}%") | User.username.like(f"%{keyword}%"))
    if departmentId:
        stmt = stmt.where(User.department_id == departmentId)
    if status:
        stmt = stmt.where(User.status == status)
    if seatStatus:
        stmt = stmt.where(User.seat_status == seatStatus)
    return success(paginate([user_dto(db, u) for u in db.execute(stmt.order_by(User.created_at.desc())).scalars().all()], page, pageSize), request.state.request_id)


def org_sync_job_dto(job: OrgSyncJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "source": job.source,
        "syncType": job.sync_type,
        "status": job.status,
        "departmentsSynced": job.departments_synced,
        "usersSynced": job.users_synced,
        "errorMessage": job.error_message,
        "payload": job.payload_snapshot,
        "operator": {"id": job.operator_id},
        "startedAt": _iso(job.started_at),
        "endedAt": _iso(job.ended_at),
        "createdAt": _iso(job.created_at),
    }


def process_org_sync_job_if_mock(db: Session, job: OrgSyncJob) -> None:
    if job.status not in {"queued", "running"}:
        return
    job.status = "running"
    job.started_at = job.started_at or now_utc()
    payload = job.payload_snapshot or {}
    departments_synced = users_synced = 0
    try:
        for dep in payload.get("departments") or []:
            dep_id = dep["id"]
            row = db.get(Department, dep_id)
            if not row:
                row = Department(id=dep_id, name=dep.get("name", dep_id), parent_id=dep.get("parentId"), status=dep.get("status", "active"), source=job.source)
                db.add(row)
            else:
                row.name = dep.get("name", row.name)
                row.parent_id = dep.get("parentId", row.parent_id)
                row.leader_id = dep.get("leaderId", row.leader_id)
                row.status = dep.get("status", row.status)
                row.source = job.source
            departments_synced += 1
        for position in payload.get("positions") or []:
            position_id = position["id"]
            row = db.get(Position, position_id)
            if not row:
                row = Position(id=position_id, name=position.get("name", position_id), department_id=position.get("departmentId"), level=position.get("level"), status=position.get("status", "active"), source=job.source)
                db.add(row)
            else:
                row.name = position.get("name", row.name)
                row.department_id = position.get("departmentId", row.department_id)
                row.level = position.get("level", row.level)
                row.status = position.get("status", row.status)
                row.source = job.source
        for item in payload.get("users") or []:
            user_id = item["id"]
            row = db.get(User, user_id)
            previous_status = row.status if row else None
            if not row:
                row = User(
                    id=user_id,
                    employee_no=item.get("employeeNo"),
                    username=item.get("username", user_id),
                    password_hash="external_identity",
                    name=item.get("name", user_id),
                    department_id=item.get("departmentId"),
                    email=item.get("email"),
                    mobile=item.get("mobile"),
                    status=item.get("status", "active"),
                    seat_status=item.get("seatStatus", "unassigned"),
                    identity_source=job.source,
                    sso_subject=item.get("ssoSubject"),
                )
                db.add(row)
            else:
                row.employee_no = item.get("employeeNo", row.employee_no)
                row.name = item.get("name", row.name)
                row.department_id = item.get("departmentId", row.department_id)
                row.email = item.get("email", row.email)
                row.mobile = item.get("mobile", row.mobile)
                row.status = item.get("status", row.status)
                row.seat_status = item.get("seatStatus", row.seat_status)
                row.identity_source = job.source
                row.sso_subject = item.get("ssoSubject", row.sso_subject)
            if row.status in {"disabled", "departed"} and previous_status != row.status:
                row.seat_status = "unassigned"
                row.locked_until = None
                for session in db.execute(select(SessionModel).where(SessionModel.user_id == row.id, SessionModel.revoked_at.is_(None))).scalars().all():
                    session.revoked_at = now_utc()
                reclaim_user_seats(db, row.id, job.operator_id, f"org_sync:{job.id}:{row.status}")
            users_synced += 1
        db.flush()
        for item in payload.get("userPositions") or []:
            exists = db.execute(select(UserPosition).where(UserPosition.user_id == item["userId"], UserPosition.position_id == item["positionId"])).scalar_one_or_none()
            if not exists and db.get(User, item["userId"]) and db.get(Position, item["positionId"]):
                db.add(UserPosition(user_id=item["userId"], position_id=item["positionId"]))
        job.departments_synced = departments_synced
        job.users_synced = users_synced
        job.status = "success"
        job.error_message = None
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)[:255]
    job.ended_at = now_utc()


@router.post("/org/sync-jobs")
def create_org_sync_job(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("security:manage"))], payload: dict[str, Any] = Body(default_factory=dict)):
    job = OrgSyncJob(
        id=new_id("org_sync"),
        source=payload.get("source", "local"),
        sync_type=payload.get("syncType", "full"),
        status="queued",
        payload_snapshot={"departments": payload.get("departments", []), "positions": payload.get("positions", []), "users": payload.get("users", []), "userPositions": payload.get("userPositions", [])},
        operator_id=auth.user.id,
    )
    db.add(job)
    audit(db, auth.user.id, "org", "sync_create", "org_sync_job", job.id, after=org_sync_job_dto(job))
    db.commit()
    return success(org_sync_job_dto(job), request.state.request_id)


@router.get("/org/sync-jobs")
def org_sync_jobs(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("security:manage"))], page: int = 1, pageSize: int = 20, status: str | None = None, source: str | None = None):
    stmt = select(OrgSyncJob)
    if status:
        stmt = stmt.where(OrgSyncJob.status == status)
    if source:
        stmt = stmt.where(OrgSyncJob.source == source)
    rows = db.execute(stmt.order_by(OrgSyncJob.created_at.desc())).scalars().all()
    return success(paginate([org_sync_job_dto(job) for job in rows], page, pageSize), request.state.request_id)


@router.get("/org/sync-jobs/{job_id}")
def org_sync_job_detail(job_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("security:manage"))]):
    job = db.get(OrgSyncJob, job_id)
    if not job:
        raise BusinessError(400001, "invalid request", 404)
    process_org_sync_job_if_mock(db, job)
    if job.status == "success":
        audit(db, auth.user.id, "org", "sync_success", "org_sync_job", job.id, after=org_sync_job_dto(job))
    elif job.status == "failed":
        audit(db, auth.user.id, "org", "sync_failed", "org_sync_job", job.id, result="failed", error=job.error_message, after=org_sync_job_dto(job))
    db.commit()
    return success(org_sync_job_dto(job), request.state.request_id)


def reclaim_user_seats(db: Session, user_id: str, actor_id: str | None, reason: str | None = None) -> list[dict[str, Any]]:
    rows = db.execute(
        select(SeatAssignment).where(
            SeatAssignment.assignee_type == "user",
            SeatAssignment.assignee_id == user_id,
            SeatAssignment.status == "active",
        )
    ).scalars().all()
    reclaimed = []
    for row in rows:
        before = seat_assignment_dto(row)
        pkg = db.get(SeatPackage, row.seat_package_id)
        if pkg and pkg.used_count > 0:
            pkg.used_count -= 1
        row.status = "reclaimed"
        after = seat_assignment_dto(row)
        reclaimed.append(after)
        record_seat_event(db, "reclaim", row, actor_id, before=before, after=after, reason=reason)
        audit(db, actor_id, "seat", "reclaim", "seat_assignment", row.id, before=before, after=after | {"reason": reason})
    return reclaimed


@router.put("/org/users/{user_id}/status")
def update_user_status(user_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("security:manage"))], payload: dict[str, Any] = Body(...)):
    user = db.get(User, user_id)
    if not user:
        raise BusinessError(400001, "invalid request", 404)
    new_status = payload.get("status")
    if new_status not in {"active", "locked", "disabled", "departed"}:
        raise BusinessError(400001, "invalid request", 422, {"field": "status"})
    before = user_dto(db, user)
    user.status = new_status
    reclaimed: list[dict[str, Any]] = []
    if new_status in {"disabled", "departed"}:
        user.seat_status = "unassigned"
        user.locked_until = None
        for session in db.execute(select(SessionModel).where(SessionModel.user_id == user.id, SessionModel.revoked_at.is_(None))).scalars().all():
            session.revoked_at = now_utc()
        reclaimed = reclaim_user_seats(db, user.id, auth.user.id, payload.get("reason"))
    audit(db, auth.user.id, "org", "user_status", "user", user.id, before=before, after=user_dto(db, user) | {"reason": payload.get("reason"), "reclaimedSeats": reclaimed})
    db.commit()
    return success(user_dto(db, user) | {"reclaimedSeats": reclaimed}, request.state.request_id)


@router.post("/org/users/{user_id}/password-reset")
def reset_user_password(user_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("security:manage"))], payload: dict[str, Any] = Body(...)):
    user = db.get(User, user_id)
    if not user:
        raise BusinessError(400001, "invalid request", 404)
    new_password = payload.get("newPassword")
    if not new_password or len(new_password) < 8:
        raise BusinessError(400001, "invalid request", 422, {"field": "newPassword", "reason": "password_too_short"})
    before = {"status": user.status, "failedLoginCount": user.failed_login_count}
    user.password_hash = hash_password(new_password)
    user.password_updated_at = now_utc()
    user.failed_login_count = 0
    user.locked_until = None
    revoked = 0
    for session in db.execute(select(SessionModel).where(SessionModel.user_id == user.id, SessionModel.revoked_at.is_(None))).scalars().all():
        session.revoked_at = now_utc()
        revoked += 1
    audit(db, auth.user.id, "org", "password_reset", "user", user.id, before=before, after={"revokedSessions": revoked, "reason": payload.get("reason")})
    db.commit()
    return success({"id": user.id, "status": user.status, "revokedSessions": revoked, "passwordUpdatedAt": _iso(user.password_updated_at)}, request.state.request_id)


def role_dto(db: Session, role: Role) -> dict[str, Any]:
    permission_codes = db.execute(select(RolePermission.permission_code).where(RolePermission.role_id == role.id)).scalars().all()
    user_count = db.scalar(select(func.count()).select_from(UserRole).where(UserRole.role_id == role.id)) or 0
    return {
        "id": role.id,
        "name": role.name,
        "description": role.description,
        "dataScope": role.data_scope,
        "status": role.status,
        "permissions": permission_codes,
        "userCount": user_count,
    }


@router.get("/roles")
def roles(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("security:manage"))], page: int = 1, pageSize: int = 50, keyword: str | None = None, status: str | None = None):
    stmt = select(Role)
    if keyword:
        stmt = stmt.where((func.lower(Role.name).like(f"%{keyword.lower()}%")) | (func.lower(Role.id).like(f"%{keyword.lower()}%")))
    if status:
        stmt = stmt.where(Role.status == status)
    rows = db.execute(stmt.order_by(Role.id.asc())).scalars().all()
    return success(paginate([role_dto(db, role) for role in rows], page, pageSize), request.state.request_id)


@router.post("/roles")
def create_role(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("security:manage"))], payload: dict[str, Any] = Body(...)):
    role = Role(id=payload.get("id") or new_id("role"), name=payload["name"], description=payload.get("description"), data_scope=payload.get("dataScope", {"type": "self", "departmentIds": []}), status=payload.get("status", "active"))
    db.add(role)
    for code in payload.get("permissions", []):
        if db.get(Permission, code):
            db.add(RolePermission(role_id=role.id, permission_code=code))
    audit(db, auth.user.id, "rbac", "create_role", "role", role.id, after={"name": role.name, "permissions": payload.get("permissions", [])})
    db.commit()
    return success(role_dto(db, role), request.state.request_id)


@router.put("/roles/{role_id}")
def update_role(role_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("security:manage"))], payload: dict[str, Any] = Body(...)):
    role = db.get(Role, role_id)
    if not role:
        raise BusinessError(400001, "invalid request", 404)
    before = role_dto(db, role)
    role.name = payload.get("name", role.name)
    role.description = payload.get("description", role.description)
    role.data_scope = payload.get("dataScope", role.data_scope)
    role.status = payload.get("status", role.status)
    audit(db, auth.user.id, "rbac", "update_role", "role", role.id, before=before, after={"name": role.name, "dataScope": role.data_scope, "status": role.status})
    db.commit()
    return success(role_dto(db, role), request.state.request_id)


@router.delete("/roles/{role_id}")
def delete_role(role_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("security:manage"))]):
    role = db.get(Role, role_id)
    if role:
        role.status = "disabled"
        audit(db, auth.user.id, "rbac", "delete_role", "role", role.id, after={"status": role.status})
        db.commit()
    return success({}, request.state.request_id)


@router.get("/permissions")
def permissions(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("security:manage"))]):
    rows = db.execute(select(Permission).order_by(Permission.module.asc(), Permission.page.asc(), Permission.action.asc())).scalars().all()
    return success([{"code": p.code, "module": p.module, "page": p.page, "action": p.action, "riskLevel": p.risk_level} for p in rows], request.state.request_id)


@router.get("/permission-matrix")
def permission_matrix(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("security:manage"))]):
    rows = db.execute(select(Permission).order_by(Permission.module.asc(), Permission.page.asc(), Permission.action.asc())).scalars().all()
    matrix: dict[str, dict[str, Any]] = {}
    for permission in rows:
        module = matrix.setdefault(permission.module, {"module": permission.module, "pages": {}})
        page_key = permission.page or "_global"
        page = module["pages"].setdefault(page_key, {"page": permission.page, "permissions": []})
        page["permissions"].append({"code": permission.code, "action": permission.action, "riskLevel": permission.risk_level})
    data = []
    for module in matrix.values():
        module["pages"] = list(module["pages"].values())
        data.append(module)
    return success(data, request.state.request_id)


@router.put("/roles/{role_id}/permissions")
def update_role_permissions(role_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("security:manage"))], payload: dict[str, Any] = Body(...)):
    role = db.get(Role, role_id)
    if not role:
        raise BusinessError(400001, "invalid request", 404)
    before = role_dto(db, role)
    existing = db.execute(select(RolePermission).where(RolePermission.role_id == role_id)).scalars().all()
    for item in existing:
        db.delete(item)
    db.flush()
    accepted_permissions = []
    for code in payload.get("permissions", []):
        if db.get(Permission, code):
            db.add(RolePermission(role_id=role_id, permission_code=code))
            accepted_permissions.append(code)
    audit(db, auth.user.id, "rbac", "update_role_permissions", "role", role_id, before=before, after={"permissions": accepted_permissions})
    db.commit()
    return success({"roleId": role_id, "permissions": accepted_permissions}, request.state.request_id)


@router.get("/models")
def models(db: Db, request: Request, auth: Auth, page: int = 1, pageSize: int = 20, keyword: str | None = None, status: str | None = None, provider: str | None = None, type: str | None = None):
    stmt = select(LlmModel)
    if keyword:
        stmt = stmt.where(LlmModel.name.like(f"%{keyword}%"))
    if status:
        stmt = stmt.where(LlmModel.status == status)
    if provider:
        stmt = stmt.where(LlmModel.provider == provider)
    if type:
        stmt = stmt.where(LlmModel.type == type)
    return success(paginate([model_dto(m) for m in db.execute(stmt).scalars().all()], page, pageSize), request.state.request_id)


def model_dto(model: LlmModel) -> dict[str, Any]:
    return {"id": model.id, "name": model.name, "provider": model.provider, "modelKey": model.model_key, "type": model.type, "baseUrl": model.base_url, "authType": model.auth_type, "secretRef": model.secret_ref, "apiKeyMasked": model.api_key_masked, "status": model.status, "unitPrice": model.unit_price, "contextLength": model.context_length, "applicableScenarios": model.applicable_scenarios or [], "defaultTimeoutMs": model.default_timeout_ms, "errorRate": model.error_rate, "avgLatencyMs": model.avg_latency_ms, "todayCallCount": model.today_call_count, "todayTokens": model.today_tokens, "containerCost": model.container_cost}


MODEL_UPDATE_FIELDS = {
    "name": "name",
    "provider": "provider",
    "modelKey": "model_key",
    "type": "type",
    "baseUrl": "base_url",
    "authType": "auth_type",
    "unitPrice": "unit_price",
    "contextLength": "context_length",
    "applicableScenarios": "applicable_scenarios",
    "defaultTimeoutMs": "default_timeout_ms",
    "errorRate": "error_rate",
    "status": "status",
}


def apply_model_change_snapshot(db: Session, approval: ApprovalRequest, actor_id: str | None) -> LlmModel:
    snapshot = approval.payload_snapshot or {}
    model = db.get(LlmModel, snapshot.get("modelId"))
    if not model:
        raise BusinessError(400001, "invalid request", 404, {"field": "modelId"})
    before = model_dto(model)
    changes = dict(snapshot.get("changes") or {})
    for api_field, attr in MODEL_UPDATE_FIELDS.items():
        if api_field in changes:
            setattr(model, attr, changes[api_field])
    if snapshot.get("secretRef"):
        model.secret_ref = snapshot["secretRef"]
        model.api_key_masked = snapshot.get("apiKeyMasked")
        record_sensitive_event(db, actor_id, "secret_write", "rotate_model_secret", "model", model.id, "high", detail={"secretRef": model.secret_ref, "apiKeyMasked": model.api_key_masked, "approvalId": approval.id})
    audit(db, actor_id, "model", "update", "model", model.id, before=before, after=model_dto(model) | {"approvalId": approval.id})
    return model


@router.post("/models")
def create_model(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("model:manage"))], payload: dict[str, Any] = Body(...)):
    api_key = payload.get("apiKey")
    model = LlmModel(id=new_id("m"), name=payload["name"], provider=payload["provider"], model_key=payload["modelKey"], type=payload["type"], base_url=payload["baseUrl"], auth_type=payload.get("authType", "api_key"), secret_ref=new_id("sec"), api_key_masked=mask_secret(api_key), status="enabled", unit_price=payload.get("unitPrice", 0), context_length=payload.get("contextLength", 0), applicable_scenarios=payload.get("applicableScenarios", []), default_timeout_ms=payload.get("defaultTimeoutMs", 300000), error_rate=payload.get("errorRate", 0))
    db.add(model)
    record_sensitive_event(db, auth.user.id, "secret_write", "create_model_secret", "model", model.id, "high", detail={"secretRef": model.secret_ref, "apiKeyMasked": model.api_key_masked})
    audit(db, auth.user.id, "model", "create", "model", model.id)
    db.commit()
    return success(model_dto(model), request.state.request_id)


@router.put("/models/{model_id}")
def update_model(model_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("model:manage"))], payload: dict[str, Any] = Body(...)):
    model = db.get(LlmModel, model_id)
    if not model:
        raise BusinessError(400001, "invalid request", 404)
    approval_id = payload.get("approvalId")
    if approval_id:
        approval = db.get(ApprovalRequest, approval_id)
        if not approval or approval.type != "model_secret_change":
            raise BusinessError(400001, "invalid request", 404, {"field": "approvalId"})
        if approval.status != "approved":
            raise BusinessError(APPROVAL_REQUIRED, "approval required", 409, {"approvalId": approval.id, "status": approval.status})
        if (approval.payload_snapshot or {}).get("modelId") != model_id:
            raise BusinessError(400001, "invalid request", 422, {"field": "approvalId"})
        model = apply_model_change_snapshot(db, approval, auth.user.id)
        db.commit()
        return success(model_dto(model), request.state.request_id)
    if "apiKey" in payload:
        changes = {api_field: payload[api_field] for api_field in MODEL_UPDATE_FIELDS if api_field in payload}
        snapshot = {
            "modelId": model_id,
            "changes": changes,
            "secretRef": new_id("sec"),
            "apiKeyMasked": mask_secret(payload.get("apiKey")),
        }
        approval = ApprovalRequest(
            id=new_id("apr"),
            type="model_secret_change",
            risk_level="high",
            applicant_id=auth.user.id,
            status="pending",
            reason=payload.get("reason", "model secret change"),
            payload_snapshot=snapshot,
        )
        db.add(approval)
        db.flush()
        ensure_approval_step(db, approval)
        audit(db, auth.user.id, "model", "request_secret_change", "approval", approval.id, after=snapshot)
        db.commit()
        return success({"status": "pending_approval", "approvalId": approval.id, "payload": snapshot}, request.state.request_id)
    before = model_dto(model)
    for api_field, attr in MODEL_UPDATE_FIELDS.items():
        if api_field in payload:
            setattr(model, attr, payload[api_field])
    audit(db, auth.user.id, "model", "update", "model", model.id, before=before, after=model_dto(model))
    db.commit()
    return success(model_dto(model), request.state.request_id)


@router.get("/models/{model_id}")
def model_detail(model_id: str, db: Db, request: Request, auth: Auth):
    model = db.get(LlmModel, model_id)
    if not model:
        raise BusinessError(400001, "invalid request", 404)
    return success(model_dto(model), request.state.request_id)


@router.get("/models/{model_id}/secret")
def model_secret_view(model_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("model:secret_view"))]):
    model = db.get(LlmModel, model_id)
    if not model:
        raise BusinessError(400001, "invalid request", 404)
    record_sensitive_event(db, auth.user.id, "secret_view", "view_model_secret", "model", model.id, "critical", detail={"secretRef": model.secret_ref, "apiKeyMasked": model.api_key_masked})
    audit(db, auth.user.id, "model", "secret_view", "model", model.id, after={"secretRef": model.secret_ref, "apiKeyMasked": model.api_key_masked})
    db.commit()
    return success({"modelId": model.id, "secretRef": model.secret_ref, "apiKeyMasked": model.api_key_masked}, request.state.request_id)


@router.post("/models/{model_id}/enable")
@router.post("/models/{model_id}/disable")
@router.post("/models/{model_id}/probe")
def model_action(model_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("model:manage"))], payload: dict[str, Any] = Body(default_factory=dict)):
    action = request.url.path.rsplit("/", 1)[-1]
    model = db.get(LlmModel, model_id)
    if not model:
        raise BusinessError(400001, "invalid request", 404)
    probe_result = None
    alert_id = None
    if action == "enable":
        model.status = "enabled"
    elif action == "disable":
        model.status = "disabled"
    elif action == "probe":
        should_fail = bool(payload.get("forceFail")) or "fail" in (model.base_url or "").lower()
        if should_fail:
            model.status = "abnormal"
            model.avg_latency_ms = 0
            alert = Alert(
                id=new_id("alt"),
                level="P1",
                status="pending",
                source_type="model",
                source_id=model.id,
                category="model_gateway",
                error_code="MODEL_PROBE_FAILED",
                title=f"模型探针失败: {model.name}",
                detail=payload.get("errorMessage") or "model probe failed",
                root_cause="model endpoint probe failed",
                suggestion="check baseUrl, credentials, network and route policy",
            )
            db.add(alert)
            alert_id = alert.id
            probe_result = "failed"
            audit(db, auth.user.id, "model", "probe_failed", "model", model.id, after={"alertId": alert.id})
        else:
            model.status = "enabled"
            model.avg_latency_ms = int(payload.get("latencyMs", 50))
            probe_result = "ok"
            audit(db, auth.user.id, "model", "probe", "model", model.id, after={"latencyMs": model.avg_latency_ms})
    else:
        raise BusinessError(400001, "invalid request", 404)
    if action in {"enable", "disable"}:
        audit(db, auth.user.id, "model", action, "model", model.id)
    db.commit()
    return success(model_dto(model) | {"probeResult": probe_result, "alertId": alert_id}, request.state.request_id)


@router.get("/model-call-logs")
@router.get("/audit/model-call-logs")
def model_logs(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("audit:view"))], page: int = 1, pageSize: int = 20, modelId: str | None = None, agentId: str | None = None, userId: str | None = None, departmentId: str | None = None, projectId: str | None = None, status: str | None = None, startTime: str | None = None, endTime: str | None = None):
    stmt = select(ModelCallLog)
    if modelId:
        stmt = stmt.where(ModelCallLog.model_id == modelId)
    if agentId:
        stmt = stmt.where(ModelCallLog.agent_id == agentId)
    if userId:
        stmt = stmt.where(ModelCallLog.user_id == userId)
    if departmentId:
        stmt = stmt.where(ModelCallLog.department_id == departmentId)
    if projectId:
        stmt = stmt.where(ModelCallLog.project_id == projectId)
    if status:
        stmt = stmt.where(ModelCallLog.status == status)
    if start := _parse_dt(startTime):
        stmt = stmt.where(ModelCallLog.created_at >= start)
    if end := _parse_dt(endTime):
        stmt = stmt.where(ModelCallLog.created_at <= end)
    logs = db.execute(stmt.order_by(ModelCallLog.created_at.desc())).scalars().all()
    return success(paginate([{"id": l.id, "userId": l.user_id, "departmentId": l.department_id, "projectId": l.project_id, "agentId": l.agent_id, "modelId": l.model_id, "inputSummary": l.input_summary, "outputSummary": l.output_summary, "latencyMs": l.latency_ms, "tokens": l.tokens, "cost": l.cost, "status": l.status, "errorCode": l.error_code, "createdAt": _iso(l.created_at)} for l in logs], page, pageSize), request.state.request_id)


@router.get("/audit/model-call-logs/export")
def model_call_logs_export(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("audit:export"))], approvalId: str | None = None):
    if not approvalId:
        query = {k: v for k, v in dict(request.query_params).items() if k != "approvalId"}
        approval = ApprovalRequest(
            id=new_id("apr"),
            type="model_call_logs_export",
            risk_level="high",
            applicant_id=auth.user.id,
            status="pending",
            reason="model call logs export",
            payload_snapshot={"exportType": "model_call_logs", "query": query},
        )
        db.add(approval)
        db.flush()
        ensure_approval_step(db, approval)
        audit(db, auth.user.id, "export", "request_approval", "approval", approval.id, after=approval.payload_snapshot)
        db.commit()
        return success({"status": "pending_approval", "approvalId": approval.id, "payload": approval.payload_snapshot}, request.state.request_id)
    query = approved_export_query(db, approvalId, "model_call_logs_export")
    task = create_export_task(db, auth, "model_call_logs", query, approval_id=approvalId)
    db.commit()
    return success({"taskId": task.id, "status": task.status, "downloadUrl": task.file_url, "watermark": task.watermark, "approvalId": approvalId, "query": task.query_snapshot}, request.state.request_id)


@router.get("/skills")
def skills(
    db: Db,
    request: Request,
    auth: Auth,
    keyword: str | None = None,
    status: str | None = None,
    source: str | None = None,
    category: str | None = None,
    page: int = 1,
    pageSize: int = 20,
):
    stmt = select(Skill)
    if keyword:
        like = f"%{keyword.lower()}%"
        stmt = stmt.where((func.lower(Skill.name).like(like)) | (func.lower(Skill.package_name).like(like)))
    if status:
        stmt = stmt.where(Skill.status == status)
    if source:
        stmt = stmt.where(Skill.source == source)
    if category:
        stmt = stmt.where(Skill.category == category)
    rows = db.execute(stmt.order_by(Skill.updated_at.desc())).scalars().all()
    data = []
    for skill in rows:
        creator = db.get(User, skill.creator_id) if skill.creator_id else None
        bound_count = db.scalar(select(func.count()).select_from(AgentBindSkill).where(AgentBindSkill.skill_id == skill.id)) or 0
        data.append(
            {
                "id": skill.id,
                "name": skill.name,
                "packageName": skill.package_name,
                "packageUrl": skill.package_url,
                "source": skill.source,
                "version": skill.version,
                "status": skill.status,
                "category": skill.category,
                "creator": {"id": skill.creator_id, "name": creator.name if creator else None},
                "updatedAt": _iso(skill.updated_at),
                "boundAgentCount": bound_count,
                "allowedRoles": skill.allowed_roles,
                "securityReviewStatus": skill.security_review_status,
            }
        )
    return success(paginate(data, page, pageSize), request.state.request_id)


def skill_scan_result(payload: dict[str, Any]) -> dict[str, Any]:
    package_url = payload.get("packageUrl") or ""
    package_name = payload.get("packageName", payload.get("name", ""))
    source = payload.get("source", "custom")
    allowed_sources = {"official", "custom", "third_party", "offline", "url", "marketplace"}
    findings = []
    if source not in allowed_sources:
        findings.append({"type": "source", "level": "high", "message": "unsupported source"})
    if source in {"offline", "url", "third_party", "marketplace"} and not package_url:
        findings.append({"type": "package", "level": "medium", "message": "package url is required for imported skill"})
    if " " in package_name:
        findings.append({"type": "format", "level": "medium", "message": "package name must not contain spaces"})
    if payload.get("forceScanFail"):
        findings.append({"type": "security", "level": "critical", "message": payload.get("scanError", "security scan failed")})
    status = "failed" if any(item["level"] in {"high", "critical"} for item in findings) else "passed"
    return {"status": status, "findings": findings, "checked": ["format", "dependency", "security"]}


def skill_version_dto(version: SkillVersion) -> dict[str, Any]:
    return {"id": version.id, "skillId": version.skill_id, "version": version.version, "packageUrl": version.package_url, "source": version.source, "scanStatus": version.scan_status, "scanResult": version.scan_result, "createdBy": version.created_by, "createdAt": _iso(version.created_at)}


def skill_review_dto(review: SkillReview) -> dict[str, Any]:
    return {"id": review.id, "skillId": review.skill_id, "reviewerId": review.reviewer_id, "decision": review.decision, "comment": review.comment, "securityScanSnapshot": review.security_scan_snapshot, "createdAt": _iso(review.created_at)}


def skill_grant_dto(grant: SkillGrant) -> dict[str, Any]:
    return {"id": grant.id, "skillId": grant.skill_id, "scopeType": grant.scope_type, "scopeId": grant.scope_id, "permission": grant.permission, "status": grant.status, "createdBy": grant.created_by, "createdAt": _iso(grant.created_at)}


def skill_has_grants(db: Session, skill_id: str) -> bool:
    return (db.scalar(select(func.count()).select_from(SkillGrant).where(SkillGrant.skill_id == skill_id, SkillGrant.status == "active")) or 0) > 0


def user_can_use_skill(db: Session, auth: Principal, skill: Skill, agent_id: str | None = None) -> bool:
    if skill.allowed_roles and set(skill.allowed_roles).intersection(auth.roles):
        return True
    if not skill_has_grants(db, skill.id):
        return not skill.allowed_roles or bool(set(skill.allowed_roles).intersection(auth.roles))
    clauses = []
    for role_id in auth.roles:
        clauses.append((SkillGrant.scope_type == "role") & (SkillGrant.scope_id == role_id))
    if auth.user.department_id:
        clauses.append((SkillGrant.scope_type == "department") & (SkillGrant.scope_id == auth.user.department_id))
    if agent_id:
        clauses.append((SkillGrant.scope_type == "agent") & (SkillGrant.scope_id == agent_id))
    project_ids = (auth.data_scope or {}).get("projectIds") or []
    for project_id in project_ids:
        clauses.append((SkillGrant.scope_type == "project") & (SkillGrant.scope_id == project_id))
    if not clauses:
        return False
    return db.execute(
        select(SkillGrant)
        .where(SkillGrant.skill_id == skill.id, SkillGrant.status == "active", SkillGrant.permission.in_(["install", "manage"]))
        .where(or_(*clauses))
    ).scalar_one_or_none() is not None


@router.post("/skills")
@router.post("/skills/import")
def create_skill(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("skill:manage"))], payload: dict[str, Any] = Body(...)):
    scan = skill_scan_result(payload)
    skill = Skill(id=new_id("sk"), name=payload["name"], package_name=payload.get("packageName", payload["name"]), package_url=payload.get("packageUrl"), source=payload.get("source", "custom"), version=payload.get("version", "1.0.0"), status="disabled" if scan["status"] == "failed" else "pending_review", category=payload.get("category"), creator_id=auth.user.id, allowed_roles=payload.get("allowedRoles", []), security_review_status="rejected" if scan["status"] == "failed" else "pending")
    db.add(skill)
    db.flush()
    version = SkillVersion(id=new_id("skv"), skill_id=skill.id, version=skill.version, package_url=skill.package_url, source=skill.source, scan_status=scan["status"], scan_result=scan, created_by=auth.user.id)
    db.add(version)
    audit(db, auth.user.id, "skill", "import", "skill", skill.id, after={"versionId": version.id, "scanStatus": scan["status"]})
    db.commit()
    return success({"id": skill.id, "status": skill.status, "versionId": version.id, "scanStatus": scan["status"], "scanResult": scan}, request.state.request_id)


@router.post("/skills/{skill_id}/review")
def review_skill(skill_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("skill:manage"))], payload: dict[str, Any] = Body(...)):
    skill = db.get(Skill, skill_id)
    if not skill:
        raise BusinessError(400001, "invalid request", 404)
    approved = payload.get("decision", "approved") == "approved"
    latest = db.execute(select(SkillVersion).where(SkillVersion.skill_id == skill.id).order_by(SkillVersion.created_at.desc())).scalars().first()
    if approved and latest and latest.scan_status != "passed":
        raise BusinessError(INVALID_STATE, "skill security scan not passed", 409, {"scanStatus": latest.scan_status})
    skill.security_review_status = "approved" if approved else "rejected"
    skill.status = "enabled" if approved else "disabled"
    review = SkillReview(id=new_id("skr"), skill_id=skill.id, reviewer_id=auth.user.id, decision="approved" if approved else "rejected", comment=payload.get("comment"), security_scan_snapshot=latest.scan_result if latest else {})
    db.add(review)
    audit(db, auth.user.id, "skill", "review", "skill", skill.id, after=skill_review_dto(review))
    db.commit()
    return success({"id": skill.id, "status": skill.status, "securityReviewStatus": skill.security_review_status, "reviewId": review.id}, request.state.request_id)


@router.get("/skills/{skill_id}")
def skill_detail(skill_id: str, db: Db, request: Request, auth: Auth):
    skill = db.get(Skill, skill_id)
    if not skill:
        raise BusinessError(400001, "invalid request", 404)
    versions = db.execute(select(SkillVersion).where(SkillVersion.skill_id == skill.id).order_by(SkillVersion.created_at.desc())).scalars().all()
    grants = db.execute(select(SkillGrant).where(SkillGrant.skill_id == skill.id, SkillGrant.status == "active")).scalars().all()
    reviews = db.execute(select(SkillReview).where(SkillReview.skill_id == skill.id).order_by(SkillReview.created_at.desc())).scalars().all()
    return success({"id": skill.id, "name": skill.name, "packageName": skill.package_name, "packageUrl": skill.package_url, "source": skill.source, "version": skill.version, "status": skill.status, "category": skill.category, "allowedRoles": skill.allowed_roles, "securityReviewStatus": skill.security_review_status, "versions": [skill_version_dto(v) for v in versions], "grants": [skill_grant_dto(g) for g in grants], "reviews": [skill_review_dto(r) for r in reviews]}, request.state.request_id)


@router.put("/skills/{skill_id}")
def update_skill(skill_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("skill:manage"))], payload: dict[str, Any] = Body(...)):
    skill = db.get(Skill, skill_id)
    if not skill:
        raise BusinessError(400001, "invalid request", 404)
    skill.name = payload.get("name", skill.name)
    skill.package_name = payload.get("packageName", skill.package_name)
    skill.package_url = payload.get("packageUrl", skill.package_url)
    if "version" in payload and payload["version"] != skill.version:
        scan = skill_scan_result(payload | {"name": skill.name, "packageName": payload.get("packageName", skill.package_name), "source": payload.get("source", skill.source), "packageUrl": payload.get("packageUrl", skill.package_url)})
        skill.version = payload["version"]
        skill.security_review_status = "pending" if scan["status"] == "passed" else "rejected"
        skill.status = "pending_review" if scan["status"] == "passed" else "disabled"
        db.add(SkillVersion(id=new_id("skv"), skill_id=skill.id, version=skill.version, package_url=skill.package_url, source=skill.source, scan_status=scan["status"], scan_result=scan, created_by=auth.user.id))
    else:
        skill.version = payload.get("version", skill.version)
    skill.status = payload.get("status", skill.status)
    skill.category = payload.get("category", skill.category)
    skill.allowed_roles = payload.get("allowedRoles", skill.allowed_roles)
    audit(db, auth.user.id, "skill", "update", "skill", skill.id, after={"version": skill.version, "status": skill.status})
    db.commit()
    return success({"id": skill.id, "name": skill.name, "packageName": skill.package_name, "version": skill.version, "status": skill.status}, request.state.request_id)


@router.get("/skills/{skill_id}/versions")
def skill_versions(skill_id: str, db: Db, request: Request, auth: Auth):
    rows = db.execute(select(SkillVersion).where(SkillVersion.skill_id == skill_id).order_by(SkillVersion.created_at.desc())).scalars().all()
    return success({"items": [skill_version_dto(v) for v in rows]}, request.state.request_id)


@router.get("/skills/{skill_id}/reviews")
def skill_reviews(skill_id: str, db: Db, request: Request, auth: Auth):
    rows = db.execute(select(SkillReview).where(SkillReview.skill_id == skill_id).order_by(SkillReview.created_at.desc())).scalars().all()
    return success({"items": [skill_review_dto(r) for r in rows]}, request.state.request_id)


@router.get("/skills/{skill_id}/grants")
def skill_grants(skill_id: str, db: Db, request: Request, auth: Auth):
    rows = db.execute(select(SkillGrant).where(SkillGrant.skill_id == skill_id).order_by(SkillGrant.created_at.desc())).scalars().all()
    return success({"items": [skill_grant_dto(g) for g in rows]}, request.state.request_id)


@router.post("/skills/{skill_id}/grants")
def create_skill_grant(skill_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("skill:manage"))], payload: dict[str, Any] = Body(...)):
    if not db.get(Skill, skill_id):
        raise BusinessError(400001, "invalid request", 404)
    existing = db.execute(select(SkillGrant).where(SkillGrant.skill_id == skill_id, SkillGrant.scope_type == payload["scopeType"], SkillGrant.scope_id == payload["scopeId"])).scalar_one_or_none()
    if existing:
        existing.permission = payload.get("permission", existing.permission)
        existing.status = payload.get("status", "active")
        grant = existing
    else:
        grant = SkillGrant(id=new_id("skg"), skill_id=skill_id, scope_type=payload["scopeType"], scope_id=payload["scopeId"], permission=payload.get("permission", "install"), status="active", created_by=auth.user.id)
        db.add(grant)
    audit(db, auth.user.id, "skill", "grant", "skill", skill_id, after=skill_grant_dto(grant))
    db.commit()
    return success(skill_grant_dto(grant), request.state.request_id)


@router.post("/agents/{agent_id}/skills/{skill_id}/install")
@router.post("/agents/{agent_id}/skills/{skill_id}/uninstall")
def bind_skill(agent_id: str, skill_id: str, db: Db, request: Request, auth: Auth):
    action = request.url.path.rsplit("/", 1)[-1]
    skill = db.get(Skill, skill_id)
    if not skill or skill.status != "enabled":
        raise BusinessError(400001, "invalid request", 422)
    if not user_can_use_skill(db, auth, skill, agent_id):
        deny_business_permission(db, auth, "skill:install", {"skillId": skill_id})
    existing = db.execute(select(AgentBindSkill).where(AgentBindSkill.agent_id == agent_id, AgentBindSkill.skill_id == skill_id)).scalar_one_or_none()
    if action == "install":
        if not existing:
            db.add(AgentBindSkill(agent_id=agent_id, skill_id=skill_id, package_name=skill.package_name, installed_version=skill.version, status="installed"))
    elif action == "uninstall":
        if existing:
            db.delete(existing)
    else:
        raise BusinessError(400001, "invalid request", 404)
    audit(db, auth.user.id, "skill", action, "agent", agent_id, after={"skillId": skill_id})
    db.commit()
    return success({"agentId": agent_id, "skillId": skill_id, "status": "installed" if action == "install" else "uninstalled"}, request.state.request_id)


@router.get("/knowledge-bases")
def knowledge_bases(db: Db, request: Request, auth: Auth):
    rows = db.execute(select(KnowledgeBase)).scalars().all()
    return success([knowledge_base_dto(kb) for kb in rows if user_can_access_knowledge(db, auth, kb)], request.state.request_id)


@router.post("/knowledge-bases")
def create_kb(db: Db, request: Request, auth: Auth, payload: dict[str, Any] = Body(...)):
    kb = KnowledgeBase(id=new_id("kb"), name=payload["name"], scope=payload.get("scope", "department"), department_id=payload.get("departmentId"), status="enabled", file_count=0)
    db.add(kb)
    db.flush()
    seed_knowledge_grants(db, kb, auth)
    audit(db, auth.user.id, "knowledge", "create", "knowledge_base", kb.id, after=knowledge_base_dto(kb))
    db.commit()
    return success({"id": kb.id, "name": kb.name}, request.state.request_id)


def knowledge_base_dto(kb: KnowledgeBase) -> dict[str, Any]:
    return {"id": kb.id, "name": kb.name, "scope": kb.scope, "departmentId": kb.department_id, "status": kb.status, "fileCount": kb.file_count, "createdAt": _iso(kb.created_at)}


def knowledge_grant_dto(grant: KnowledgeGrant) -> dict[str, Any]:
    return {"id": grant.id, "knowledgeBaseId": grant.knowledge_base_id, "scopeType": grant.scope_type, "scopeId": grant.scope_id, "permission": grant.permission, "status": grant.status, "createdBy": grant.created_by, "createdAt": _iso(grant.created_at)}


def seed_knowledge_grants(db: Session, kb: KnowledgeBase, auth: Principal) -> None:
    db.add(KnowledgeGrant(id=new_id("kbg"), knowledge_base_id=kb.id, scope_type="user", scope_id=auth.user.id, permission="manage", created_by=auth.user.id))
    if kb.scope == "department" and kb.department_id:
        db.add(KnowledgeGrant(id=new_id("kbg"), knowledge_base_id=kb.id, scope_type="department", scope_id=kb.department_id, permission="read", created_by=auth.user.id))
    if kb.scope == "enterprise":
        db.add(KnowledgeGrant(id=new_id("kbg"), knowledge_base_id=kb.id, scope_type="enterprise", scope_id="all", permission="read", created_by=auth.user.id))


def user_can_access_knowledge(db: Session, auth: Principal, kb: KnowledgeBase, agent_id: str | None = None, permissions: set[str] | None = None) -> bool:
    permissions = permissions or {"read", "manage"}
    if (auth.data_scope or {}).get("type") == "all":
        return True
    if kb.scope == "enterprise":
        return True
    clauses = [(KnowledgeGrant.scope_type == "user") & (KnowledgeGrant.scope_id == auth.user.id)]
    if auth.user.department_id:
        clauses.append((KnowledgeGrant.scope_type == "department") & (KnowledgeGrant.scope_id == auth.user.department_id))
    if agent_id:
        clauses.append((KnowledgeGrant.scope_type == "agent") & (KnowledgeGrant.scope_id == agent_id))
    for project_id in (auth.data_scope or {}).get("projectIds") or []:
        clauses.append((KnowledgeGrant.scope_type == "project") & (KnowledgeGrant.scope_id == project_id))
    grant = db.execute(
        select(KnowledgeGrant)
        .where(KnowledgeGrant.knowledge_base_id == kb.id, KnowledgeGrant.status == "active", KnowledgeGrant.permission.in_(list(permissions)))
        .where(or_(*clauses))
    ).scalar_one_or_none()
    return grant is not None


def deny_business_permission(db: Session, auth: Principal, permission_code: str, data: dict[str, Any] | None = None) -> None:
    db.rollback()
    record_permission_denied(db, auth.user.id, permission_code)
    raise BusinessError(FORBIDDEN, "forbidden", 403, data)


@router.get("/knowledge-bases/{kb_id}/grants")
def knowledge_grants(kb_id: str, db: Db, request: Request, auth: Auth):
    kb = db.get(KnowledgeBase, kb_id)
    if not kb:
        raise BusinessError(400001, "invalid request", 404)
    if not user_can_access_knowledge(db, auth, kb, permissions={"manage"}):
        deny_business_permission(db, auth, "knowledge:manage", {"knowledgeBaseId": kb_id})
    rows = db.execute(select(KnowledgeGrant).where(KnowledgeGrant.knowledge_base_id == kb_id).order_by(KnowledgeGrant.created_at.desc())).scalars().all()
    return success({"items": [knowledge_grant_dto(row) for row in rows]}, request.state.request_id)


@router.post("/knowledge-bases/{kb_id}/grants")
def create_knowledge_grant(kb_id: str, db: Db, request: Request, auth: Auth, payload: dict[str, Any] = Body(...)):
    kb = db.get(KnowledgeBase, kb_id)
    if not kb:
        raise BusinessError(400001, "invalid request", 404)
    if not user_can_access_knowledge(db, auth, kb, permissions={"manage"}):
        deny_business_permission(db, auth, "knowledge:manage", {"knowledgeBaseId": kb_id})
    existing = db.execute(select(KnowledgeGrant).where(KnowledgeGrant.knowledge_base_id == kb_id, KnowledgeGrant.scope_type == payload["scopeType"], KnowledgeGrant.scope_id == payload["scopeId"])).scalar_one_or_none()
    if existing:
        existing.permission = payload.get("permission", existing.permission)
        existing.status = payload.get("status", "active")
        grant = existing
    else:
        grant = KnowledgeGrant(id=new_id("kbg"), knowledge_base_id=kb_id, scope_type=payload["scopeType"], scope_id=payload["scopeId"], permission=payload.get("permission", "read"), status="active", created_by=auth.user.id)
        db.add(grant)
    audit(db, auth.user.id, "knowledge", "grant", "knowledge_base", kb_id, after=knowledge_grant_dto(grant))
    db.commit()
    return success(knowledge_grant_dto(grant), request.state.request_id)


@router.get("/knowledge-bases/{kb_id}/files")
def kb_files(kb_id: str, db: Db, request: Request, auth: Auth):
    kb = db.get(KnowledgeBase, kb_id)
    if not kb:
        raise BusinessError(400001, "invalid request", 404)
    if not user_can_access_knowledge(db, auth, kb):
        deny_business_permission(db, auth, "knowledge:access", {"knowledgeBaseId": kb_id})
    rows = db.execute(select(KnowledgeFile).where(KnowledgeFile.knowledge_base_id == kb_id)).scalars().all()
    data = []
    for file in rows:
        task = db.execute(select(KnowledgeParseTask).where(KnowledgeParseTask.file_id == file.id).order_by(KnowledgeParseTask.created_at.desc())).scalars().first()
        process_parse_task_if_mock(file, task)
        data.append({"id": file.id, "filename": file.filename, "fileType": file.file_type, "sizeBytes": file.size_bytes, "status": file.status, "parseTask": parse_task_dto(task), "createdAt": _iso(file.created_at)})
    db.commit()
    return success(data, request.state.request_id)


@router.post("/knowledge-bases/{kb_id}/files")
def create_kb_file(kb_id: str, db: Db, request: Request, auth: Auth, payload: dict[str, Any] = Body(default_factory=dict)):
    kb = db.get(KnowledgeBase, kb_id)
    if not kb:
        raise BusinessError(400001, "invalid request", 404)
    if not user_can_access_knowledge(db, auth, kb, permissions={"manage"}):
        deny_business_permission(db, auth, "knowledge:manage", {"knowledgeBaseId": kb_id})
    file_type = payload.get("fileType", "txt").lower()
    passed, validation_error = validate_file_security(payload | {"fileType": file_type})
    status = "uploaded" if passed else "failed"
    file = KnowledgeFile(id=new_id("kf"), knowledge_base_id=kb_id, filename=payload.get("filename", "uploaded.txt"), file_type=file_type, size_bytes=payload.get("sizeBytes", 0), status=status, parse_error=validation_error)
    db.add(file)
    kb.file_count += 1
    task = create_parse_task(db, file)
    if validation_error:
        task.status = "failed"
        task.phase = "validating"
        task.error_message = validation_error
        audit(db, auth.user.id, "knowledge", "upload_rejected", "knowledge_file", file.id, result="failed", error=validation_error, after={"knowledgeBaseId": kb_id, "filename": file.filename, "fileType": file.file_type, "sizeBytes": file.size_bytes})
    db.commit()
    return success({"id": file.id, "status": file.status, "parseTaskId": task.id, "parseError": file.parse_error}, request.state.request_id)


@router.delete("/knowledge-files/{file_id}")
def delete_knowledge_file(file_id: str, db: Db, request: Request, auth: Auth):
    file = db.get(KnowledgeFile, file_id)
    if not file:
        return success({}, request.state.request_id)
    references = db.execute(
        select(AgentBindKnowledge, Agent)
        .join(Agent, Agent.id == AgentBindKnowledge.agent_id)
        .where(AgentBindKnowledge.knowledge_base_id == file.knowledge_base_id, Agent.deleted_at.is_(None))
    ).all()
    if references:
        raise BusinessError(
            INVALID_STATE,
            "knowledge file is referenced",
            409,
            {
                "fileId": file.id,
                "knowledgeBaseId": file.knowledge_base_id,
                "references": [
                    {"agentId": agent.id, "agentName": agent.name, "scope": bind.scope}
                    for bind, agent in references
                ],
            },
        )
    for task in db.execute(select(KnowledgeParseTask).where(KnowledgeParseTask.file_id == file_id)).scalars().all():
        db.delete(task)
    db.flush()
    kb = db.get(KnowledgeBase, file.knowledge_base_id)
    if kb and kb.file_count > 0:
        kb.file_count -= 1
    db.delete(file)
    audit(db, auth.user.id, "knowledge", "delete_file", "knowledge_file", file_id)
    db.commit()
    return success({}, request.state.request_id)


@router.post("/knowledge-files/{file_id}/reindex")
def reindex_knowledge_file(file_id: str, db: Db, request: Request, auth: Auth):
    file = db.get(KnowledgeFile, file_id)
    if not file:
        raise BusinessError(400001, "invalid request", 404)
    latest_task = db.execute(select(KnowledgeParseTask).where(KnowledgeParseTask.file_id == file.id).order_by(KnowledgeParseTask.created_at.desc())).scalars().first()
    before = {"status": file.status, "latestParseTaskId": latest_task.id if latest_task else None}
    file.status = "parsing"
    task = create_parse_task(db, file, "reindex")
    audit(db, auth.user.id, "knowledge", "reindex_file", "knowledge_file", file_id, before=before, after={"status": file.status, "parseTaskId": task.id})
    db.commit()
    return success({"fileId": file_id, "status": "parsing", "parseTaskId": task.id}, request.state.request_id)


def parse_task_dto(task: KnowledgeParseTask | None) -> dict[str, Any] | None:
    if not task:
        return None
    return {"id": task.id, "status": task.status, "phase": task.phase, "errorMessage": task.error_message, "createdAt": _iso(task.created_at)}


@router.post("/agents/{agent_id}/knowledge-bases/{kb_id}/bind")
def bind_kb(agent_id: str, kb_id: str, db: Db, request: Request, auth: Auth):
    agent = scoped_agent(db, auth, agent_id)
    if not agent:
        raise BusinessError(400001, "invalid request", 404)
    kb = db.get(KnowledgeBase, kb_id)
    if not kb:
        raise BusinessError(400001, "invalid request", 404)
    if not user_can_access_knowledge(db, auth, kb, agent_id=agent_id):
        deny_business_permission(db, auth, "knowledge:bind", {"knowledgeBaseId": kb_id})
    if not db.execute(select(AgentBindKnowledge).where(AgentBindKnowledge.agent_id == agent_id, AgentBindKnowledge.knowledge_base_id == kb_id)).scalar_one_or_none():
        db.add(AgentBindKnowledge(agent_id=agent_id, knowledge_base_id=kb_id, scope="read"))
    audit(db, auth.user.id, "knowledge", "bind", "agent", agent_id, after={"knowledgeBaseId": kb_id})
    db.commit()
    return success({"agentId": agent_id, "knowledgeBaseId": kb_id, "status": "bound"}, request.state.request_id)


@router.delete("/agents/{agent_id}/knowledge-bases/{kb_id}/bind")
def unbind_kb(agent_id: str, kb_id: str, db: Db, request: Request, auth: Auth):
    item = db.execute(select(AgentBindKnowledge).where(AgentBindKnowledge.agent_id == agent_id, AgentBindKnowledge.knowledge_base_id == kb_id)).scalar_one_or_none()
    if item:
        before = {"agentId": item.agent_id, "knowledgeBaseId": item.knowledge_base_id, "scope": item.scope}
        db.delete(item)
        audit(db, auth.user.id, "knowledge", "unbind", "agent", agent_id, before=before, after={"knowledgeBaseId": kb_id, "status": "unbound"})
        db.commit()
    return success({}, request.state.request_id)


@router.get("/monitor/overview")
def monitor_overview(db: Db, request: Request, auth: Auth):
    running = db.scalar(select(func.count()).select_from(Agent).where(Agent.status == "running")) or 0
    abnormal = db.scalar(select(func.count()).select_from(Agent).where(Agent.status == "abnormal")) or 0
    models_ok = db.scalar(select(func.count()).select_from(LlmModel).where(LlmModel.status == "enabled")) or 0
    abnormal_models = db.scalar(select(func.count()).select_from(LlmModel).where(LlmModel.status.in_(["abnormal", "disabled"]))) or 0
    pending_alerts = db.scalar(select(func.count()).select_from(Alert).where(Alert.status == "pending")) or 0
    today_start = datetime.combine(now_utc().date(), datetime.min.time())
    today_call_count = db.scalar(select(func.count()).select_from(ModelCallLog).where(ModelCallLog.created_at >= today_start)) or 0
    avg_latency = db.scalar(select(func.avg(ModelCallLog.latency_ms)).where(ModelCallLog.created_at >= today_start)) or 0
    runtimes = db.execute(select(AgentRuntimeSnapshot)).scalars().all()
    usage_samples = [(r.current_users / r.max_users) for r in runtimes if r.max_users]
    resource_usage_rate = round(sum(usage_samples) / len(usage_samples), 4) if usage_samples else 0
    return success({"runningAgentCount": running, "abnormalAgentCount": abnormal, "availableModelCount": models_ok, "abnormalModelCount": abnormal_models, "pendingAlertCount": pending_alerts, "todayCallCount": today_call_count, "avgLatencyMs": int(avg_latency), "resourceUsageRate": resource_usage_rate, "refreshIntervalSeconds": 5, "dataSource": "database"}, request.state.request_id)


def metric_sample_dto(sample: MetricSample) -> dict[str, Any]:
    return {"id": sample.id, "sourceType": sample.source_type, "sourceId": sample.source_id, "metricName": sample.metric_name, "value": sample.value, "dataSource": sample.data_source, "labels": sample.labels, "collectedAt": _iso(sample.collected_at)}


def alert_rule_dto(rule: AlertRule) -> dict[str, Any]:
    return {"id": rule.id, "name": rule.name, "metricName": rule.metric_name, "operator": rule.operator, "threshold": rule.threshold, "level": rule.level, "sourceType": rule.source_type, "category": rule.category, "errorCode": rule.error_code, "status": rule.status, "suggestion": rule.suggestion, "createdAt": _iso(rule.created_at), "updatedAt": _iso(rule.updated_at)}


def alert_event(db: Session, alert_id: str, action: str, actor_id: str | None, detail: dict[str, Any] | None = None) -> None:
    db.add(AlertEvent(id=new_id("ale"), alert_id=alert_id, action=action, actor_id=actor_id, detail=detail or {}))


def create_notification(
    db: Session,
    recipient_id: str | None,
    notification_type: str,
    title: str,
    content: str | None = None,
    source_type: str | None = None,
    source_id: str | None = None,
    detail: dict[str, Any] | None = None,
) -> Notification | None:
    if not recipient_id:
        return None
    existing = db.execute(
        select(Notification).where(
            Notification.recipient_id == recipient_id,
            Notification.type == notification_type,
            Notification.source_type == source_type,
            Notification.source_id == source_id,
            Notification.status == "unread",
        )
    ).scalars().first()
    if existing:
        return existing
    row = Notification(
        id=new_id("ntf"),
        recipient_id=recipient_id,
        type=notification_type,
        title=title,
        content=content,
        source_type=source_type,
        source_id=source_id,
        detail=detail or {},
    )
    db.add(row)
    return row


def notification_dto(row: Notification) -> dict[str, Any]:
    return {
        "id": row.id,
        "recipientId": row.recipient_id,
        "type": row.type,
        "title": row.title,
        "content": row.content,
        "sourceType": row.source_type,
        "sourceId": row.source_id,
        "status": row.status,
        "detail": row.detail,
        "createdAt": _iso(row.created_at),
        "readAt": _iso(row.read_at),
    }


@router.get("/notifications")
def notifications(db: Db, request: Request, auth: Auth, page: int = 1, pageSize: int = 20, status: str | None = None, type: str | None = None):
    stmt = select(Notification).where(Notification.recipient_id == auth.user.id)
    if status:
        stmt = stmt.where(Notification.status == status)
    if type:
        stmt = stmt.where(Notification.type == type)
    rows = db.execute(stmt.order_by(Notification.created_at.desc())).scalars().all()
    return success(paginate([notification_dto(row) for row in rows], page, pageSize), request.state.request_id)


@router.get("/notifications/summary")
def notification_summary(db: Db, request: Request, auth: Auth):
    rows = db.execute(select(Notification).where(Notification.recipient_id == auth.user.id)).scalars().all()
    unread = [row for row in rows if row.status == "unread"]
    by_type: dict[str, int] = {}
    for row in unread:
        by_type[row.type] = by_type.get(row.type, 0) + 1
    return success({"unreadCount": len(unread), "byType": by_type}, request.state.request_id)


@router.post("/notifications/{notification_id}/read")
def read_notification(notification_id: str, db: Db, request: Request, auth: Auth):
    row = db.get(Notification, notification_id)
    if not row or row.recipient_id != auth.user.id:
        raise BusinessError(400001, "invalid request", 404)
    before = notification_dto(row)
    row.status = "read"
    row.read_at = now_utc()
    audit(db, auth.user.id, "notification", "read", "notification", row.id, before=before, after=notification_dto(row))
    db.commit()
    return success(notification_dto(row), request.state.request_id)


@router.post("/notifications/scan-seat-expirations")
def scan_seat_expirations(db: Db, request: Request, auth: Auth):
    reminders = {30, 15, 7, 1}
    today = now_utc().date()
    created = []
    packages = db.execute(select(SeatPackage).where(SeatPackage.status == "active", SeatPackage.expires_at.is_not(None))).scalars().all()
    for pkg in packages:
        days_left = (pkg.expires_at.date() - today).days if pkg.expires_at else None
        if days_left in reminders:
            row = create_notification(
                db,
                auth.user.id,
                "seat_expiration",
                f"席位包即将到期：{pkg.name}",
                f"席位包 {pkg.name} 将在 {days_left} 天后到期",
                "seat_package",
                pkg.id,
                {"daysLeft": days_left, "expiresAt": _iso(pkg.expires_at)},
            )
            if row:
                created.append(row)
    audit(db, auth.user.id, "notification", "scan_seat_expirations", "seat_package", None, after={"created": len(created)})
    db.commit()
    return success({"createdCount": len(created), "items": [notification_dto(row) for row in created]}, request.state.request_id)


def compare_metric(value: float, operator: str, threshold: float) -> bool:
    if operator == ">":
        return value > threshold
    if operator == ">=":
        return value >= threshold
    if operator == "<":
        return value < threshold
    if operator == "<=":
        return value <= threshold
    if operator in {"==", "="}:
        return value == threshold
    return False


def alert_from_rule(db: Session, rule: AlertRule, sample: MetricSample, actor_id: str | None) -> Alert:
    existing = db.execute(
        select(Alert).where(
            Alert.source_type == rule.source_type,
            Alert.source_id == sample.source_id,
            Alert.error_code == rule.error_code,
            Alert.status.in_(["pending", "claimed", "processing", "suspended"]),
        )
    ).scalar_one_or_none()
    detail = f"{sample.metric_name}={sample.value} {rule.operator} {rule.threshold}, dataSource={sample.data_source}"
    if existing:
        existing.detail = detail
        existing.updated_at = now_utc()
        alert_event(db, existing.id, "rule_hit", actor_id, {"ruleId": rule.id, "sampleId": sample.id, "value": sample.value})
        return existing
    alert = Alert(
        id=new_id("alt"),
        level=rule.level,
        status="pending",
        source_type=rule.source_type,
        source_id=sample.source_id,
        category=rule.category,
        error_code=rule.error_code,
        title=rule.name,
        detail=detail,
        root_cause="Metric sample matched alert rule.",
        suggestion=rule.suggestion,
    )
    db.add(alert)
    alert_event(db, alert.id, "rule_hit", actor_id, {"ruleId": rule.id, "sampleId": sample.id, "value": sample.value})
    if alert.level in {"P0", "P1"}:
        db.add(DiagnosisTicket(id=new_id("diag"), level=alert.level, object_type=alert.source_type, object_id=alert.source_id, status="open", summary=alert.title, root_cause=alert.root_cause, suggestion=alert.suggestion))
    return alert


@router.get("/monitor/metrics")
def list_metrics(db: Db, request: Request, auth: Auth, sourceType: str | None = None, sourceId: str | None = None, metricName: str | None = None, page: int = 1, pageSize: int = 20):
    stmt = select(MetricSample)
    if sourceType:
        stmt = stmt.where(MetricSample.source_type == sourceType)
    if sourceId:
        stmt = stmt.where(MetricSample.source_id == sourceId)
    if metricName:
        stmt = stmt.where(MetricSample.metric_name == metricName)
    rows = db.execute(stmt.order_by(MetricSample.collected_at.desc())).scalars().all()
    return success(paginate([metric_sample_dto(row) for row in rows], page, pageSize), request.state.request_id)


@router.post("/monitor/metrics")
def collect_metrics(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("alert:manage"))], payload: dict[str, Any] = Body(...)):
    samples_payload = payload.get("samples") or [payload]
    samples: list[MetricSample] = []
    triggered: list[Alert] = []
    rules = db.execute(select(AlertRule).where(AlertRule.status == "enabled")).scalars().all()
    for item in samples_payload:
        sample = MetricSample(id=new_id("met"), source_type=item.get("sourceType", "agent"), source_id=item.get("sourceId"), metric_name=item["metricName"], value=float(item.get("value", 0)), data_source=item.get("dataSource", payload.get("dataSource", "mock")), labels=item.get("labels", {}))
        db.add(sample)
        samples.append(sample)
        for rule in rules:
            if rule.metric_name == sample.metric_name and rule.source_type == sample.source_type and compare_metric(sample.value, rule.operator, rule.threshold):
                triggered.append(alert_from_rule(db, rule, sample, auth.user.id))
    audit(db, auth.user.id, "monitor", "collect_metrics", "metric_sample", samples[0].id if samples else None, after={"sampleCount": len(samples), "triggeredAlertCount": len(triggered)})
    db.commit()
    return success({"items": [metric_sample_dto(row) for row in samples], "triggeredAlerts": [alert_dto(row) for row in triggered], "dataSource": samples[0].data_source if samples else payload.get("dataSource", "mock")}, request.state.request_id)


@router.get("/alert-rules")
def list_alert_rules(db: Db, request: Request, auth: Auth, status: str | None = None, metricName: str | None = None, page: int = 1, pageSize: int = 20):
    stmt = select(AlertRule)
    if status:
        stmt = stmt.where(AlertRule.status == status)
    if metricName:
        stmt = stmt.where(AlertRule.metric_name == metricName)
    rows = db.execute(stmt.order_by(AlertRule.created_at.desc())).scalars().all()
    return success(paginate([alert_rule_dto(row) for row in rows], page, pageSize), request.state.request_id)


@router.post("/alert-rules")
def create_alert_rule(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("alert:manage"))], payload: dict[str, Any] = Body(...)):
    rule = AlertRule(id=new_id("alr"), name=payload["name"], metric_name=payload["metricName"], operator=payload.get("operator", ">="), threshold=float(payload.get("threshold", 0)), level=payload.get("level", "P2"), source_type=payload.get("sourceType", "agent"), category=payload.get("category", "runtime"), error_code=payload.get("errorCode", "METRIC_THRESHOLD"), status=payload.get("status", "enabled"), suggestion=payload.get("suggestion"))
    db.add(rule)
    audit(db, auth.user.id, "alert", "create_rule", "alert_rule", rule.id, after=alert_rule_dto(rule))
    db.commit()
    return success(alert_rule_dto(rule), request.state.request_id)


@router.put("/alert-rules/{rule_id}")
def update_alert_rule(rule_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("alert:manage"))], payload: dict[str, Any] = Body(...)):
    rule = db.get(AlertRule, rule_id)
    if not rule:
        raise BusinessError(400001, "invalid request", 404)
    before = alert_rule_dto(rule)
    for api_field, model_field in {"name": "name", "metricName": "metric_name", "operator": "operator", "threshold": "threshold", "level": "level", "sourceType": "source_type", "category": "category", "errorCode": "error_code", "status": "status", "suggestion": "suggestion"}.items():
        if api_field in payload:
            setattr(rule, model_field, payload[api_field])
    rule.updated_at = now_utc()
    audit(db, auth.user.id, "alert", "update_rule", "alert_rule", rule.id, before=before, after=alert_rule_dto(rule))
    db.commit()
    return success(alert_rule_dto(rule), request.state.request_id)


@router.get("/alerts/{alert_id}/events")
def alert_events(alert_id: str, db: Db, request: Request, auth: Auth):
    rows = db.execute(select(AlertEvent).where(AlertEvent.alert_id == alert_id).order_by(AlertEvent.created_at.asc())).scalars().all()
    return success({"items": [{"id": row.id, "alertId": row.alert_id, "action": row.action, "actorId": row.actor_id, "detail": row.detail, "createdAt": _iso(row.created_at)} for row in rows]}, request.state.request_id)


@router.get("/alerts")
def alerts(
    db: Db,
    request: Request,
    auth: Auth,
    page: int = 1,
    pageSize: int = 20,
    level: str | None = None,
    status: str | None = None,
    sourceType: str | None = None,
    departmentId: str | None = None,
    startTime: str | None = None,
    endTime: str | None = None,
):
    stmt = select(Alert)
    if level:
        stmt = stmt.where(Alert.level == level)
    if status:
        stmt = stmt.where(Alert.status == status)
    if sourceType:
        stmt = stmt.where(Alert.source_type == sourceType)
    if departmentId:
        agent_ids = select(Agent.id).where(Agent.department_id == departmentId)
        stmt = stmt.where(Alert.source_type == "agent", Alert.source_id.in_(agent_ids))
    if start := _parse_dt(startTime):
        stmt = stmt.where(Alert.created_at >= start)
    if end := _parse_dt(endTime):
        stmt = stmt.where(Alert.created_at <= end)
    return success(paginate([alert_dto(a) for a in db.execute(stmt.order_by(Alert.created_at.desc())).scalars().all()], page, pageSize), request.state.request_id)


@router.post("/alerts")
def create_alert(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("alert:manage"))], payload: dict[str, Any] = Body(...)):
    alert = Alert(
        id=new_id("alt"),
        level=payload.get("level", "P2"),
        status="pending",
        source_type=payload.get("sourceType", "agent"),
        source_id=payload.get("sourceId"),
        category=payload.get("category", "runtime"),
        error_code=payload.get("errorCode"),
        title=payload["title"],
        detail=payload.get("detail"),
        root_cause=payload.get("rootCause"),
        suggestion=payload.get("suggestion"),
        owner_id=payload.get("ownerId"),
    )
    db.add(alert)
    db.flush()
    alert_event(db, alert.id, "create", auth.user.id, {"source": "manual"})
    create_notification(
        db,
        alert.owner_id or auth.user.id,
        "alert_created",
        f"新告警：{alert.title}",
        alert.detail,
        "alert",
        alert.id,
        {"level": alert.level, "sourceType": alert.source_type, "sourceId": alert.source_id},
    )
    diagnosis_id = None
    if alert.level in {"P0", "P1"}:
        ticket = DiagnosisTicket(
            id=new_id("diag"),
            level=alert.level,
            object_type=alert.source_type,
            object_id=alert.source_id,
            status="open",
            summary=alert.title,
            root_cause=alert.root_cause,
            suggestion=alert.suggestion,
        )
        db.add(ticket)
        diagnosis_id = ticket.id
    audit(db, auth.user.id, "alert", "create", "alert", alert.id)
    db.commit()
    return success(alert_dto(alert) | {"diagnosisId": diagnosis_id}, request.state.request_id)


def alert_dto(a: Alert) -> dict[str, Any]:
    return {"id": a.id, "alertNo": a.id, "level": a.level, "status": a.status, "sourceType": a.source_type, "sourceId": a.source_id, "sourceObject": {"type": a.source_type, "id": a.source_id}, "errorCode": a.error_code, "category": a.category, "title": a.title, "detail": a.detail, "rootCause": a.root_cause, "suggestion": a.suggestion, "ownerId": a.owner_id, "impactScope": {"sourceType": a.source_type, "sourceId": a.source_id}, "resolution": a.resolution, "triggeredAt": _iso(a.created_at), "createdAt": _iso(a.created_at), "updatedAt": _iso(a.updated_at)}


@router.get("/alerts/{alert_id}")
def alert_detail(alert_id: str, db: Db, request: Request, auth: Auth):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise BusinessError(400001, "invalid request", 404)
    return success(alert_dto(alert), request.state.request_id)


@router.post("/alerts/{alert_id}/claim")
@router.post("/alerts/{alert_id}/process")
@router.post("/alerts/{alert_id}/transfer")
@router.post("/alerts/{alert_id}/suspend")
@router.post("/alerts/{alert_id}/close")
def alert_action(alert_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("alert:manage"))], payload: dict[str, Any] = Body(default_factory=dict)):
    action = request.url.path.rsplit("/", 1)[-1]
    alert = db.get(Alert, alert_id)
    if not alert:
        raise BusinessError(400001, "invalid request", 404)
    transitions = {"claim": "claimed", "process": "processing", "transfer": "pending", "suspend": "suspended", "close": "closed"}
    if action not in transitions:
        raise BusinessError(400001, "invalid request", 404)
    before = alert_dto(alert)
    alert.status = transitions[action]
    if action == "claim":
        alert.owner_id = payload.get("ownerId", auth.user.id)
    elif action == "transfer":
        alert.owner_id = payload.get("ownerId") or payload.get("assigneeId")
        if not alert.owner_id:
            raise BusinessError(400001, "invalid request", 422, {"field": "ownerId"})
    elif payload.get("ownerId"):
        alert.owner_id = payload.get("ownerId")
    alert.resolution = payload.get("resolution", alert.resolution)
    if payload.get("detail"):
        alert.detail = payload.get("detail")
    alert.updated_at = now_utc()
    alert_event(db, alert.id, action, auth.user.id, {"comment": payload.get("comment"), "resolution": payload.get("resolution")})
    if action == "close":
        create_notification(
            db,
            alert.owner_id or auth.user.id,
            "alert_closed",
            f"告警已闭环：{alert.title}",
            payload.get("resolution") or alert.resolution,
            "alert",
            alert.id,
            {"status": alert.status, "closedBy": auth.user.id},
        )
    audit(db, auth.user.id, "alert", action, "alert", alert.id, before=before, after=alert_dto(alert) | {"comment": payload.get("comment")})
    db.commit()
    return success(alert_dto(alert), request.state.request_id)


@router.get("/diagnostics")
def diagnostics(db: Db, request: Request, auth: Auth, page: int = 1, pageSize: int = 20, level: str | None = None, objectType: str | None = None):
    stmt = select(DiagnosisTicket)
    if level:
        stmt = stmt.where(DiagnosisTicket.level == level)
    if objectType:
        stmt = stmt.where(DiagnosisTicket.object_type == objectType)
    rows = db.execute(stmt.order_by(DiagnosisTicket.created_at.desc())).scalars().all()
    return success(paginate([{"id": d.id, "level": d.level, "objectType": d.object_type, "objectId": d.object_id, "status": d.status, "summary": d.summary, "rootCause": d.root_cause, "suggestion": d.suggestion} for d in rows], page, pageSize), request.state.request_id)


@router.get("/diagnostics/{diagnosis_id}")
def diagnosis_detail(diagnosis_id: str, db: Db, request: Request, auth: Auth):
    item = db.get(DiagnosisTicket, diagnosis_id)
    if not item:
        raise BusinessError(400001, "invalid request", 404)
    return success({"id": item.id, "level": item.level, "objectType": item.object_type, "objectId": item.object_id, "status": item.status, "summary": item.summary, "rootCause": item.root_cause, "suggestion": item.suggestion}, request.state.request_id)


HIGH_RISK_OPS_TASK_TYPES = {"vulnerability_patch", "security_patch", "batch_vulnerability_fix", "node_rebuild"}


def self_heal_task_dto(task: SelfHealTask) -> dict[str, Any]:
    return {
        "id": task.id,
        "taskType": task.task_type,
        "targetType": task.target_type,
        "targetId": task.target_id,
        "status": task.status,
        "riskLevel": task.risk_level,
        "approvalId": task.approval_id,
        "diagnosisId": task.diagnosis_id,
        "payload": task.payload_snapshot,
        "result": task.result,
        "errorMessage": task.error_message,
        "operatorId": task.operator_id,
        "startedAt": _iso(task.started_at),
        "endedAt": _iso(task.ended_at),
        "createdAt": _iso(task.created_at),
    }


def create_self_heal_task(db: Session, payload: dict[str, Any], operator_id: str | None, approval_id: str | None = None) -> SelfHealTask:
    task = SelfHealTask(
        id=new_id("heal"),
        task_type=payload.get("taskType", "restart_agent"),
        target_type=payload.get("targetType", "agent"),
        target_id=payload.get("targetId"),
        status="queued",
        risk_level=payload.get("riskLevel", "normal"),
        approval_id=approval_id,
        diagnosis_id=payload.get("diagnosisId"),
        payload_snapshot=payload,
        operator_id=operator_id,
    )
    db.add(task)
    db.flush()
    process_self_heal_task_if_mock(db, task)
    return task


def process_self_heal_task_if_mock(db: Session, task: SelfHealTask) -> None:
    task.started_at = task.started_at or now_utc()
    if (task.payload_snapshot or {}).get("forceFail"):
        task.status = "failed"
        task.error_message = (task.payload_snapshot or {}).get("errorMessage", "self heal task failed")
        task.result = {"message": task.error_message}
        task.ended_at = now_utc()
        db.add(
            Alert(
                id=new_id("alt"),
                level="P1",
                status="pending",
                source_type="self_heal_task",
                source_id=task.id,
                category="ops",
                error_code="SELF_HEAL_FAILED",
                title=f"Self heal task failed: {task.task_type}",
                detail=task.error_message,
                suggestion="Review task logs and retry after resolving the root cause.",
            )
        )
        return
    task.status = "success"
    task.result = {"message": "self heal completed", "action": task.task_type}
    task.ended_at = now_utc()
    if task.diagnosis_id:
        diagnosis = db.get(DiagnosisTicket, task.diagnosis_id)
        if diagnosis:
            diagnosis.status = "fixed"
            related_alerts = db.execute(
                select(Alert).where(Alert.source_type == diagnosis.object_type, Alert.source_id == diagnosis.object_id, Alert.status != "closed")
            ).scalars().all()
            for alert in related_alerts:
                alert.status = "closed"
                alert.resolution = "诊断一键修复已执行"
            updated_inspection_count = close_related_inspection_items(db, diagnosis)
            task.result = task.result | {"closedAlertCount": len(related_alerts), "updatedInspectionItemCount": updated_inspection_count}
    elif task.target_type == "agent" and task.task_type in {"restart_agent", "cache_refresh"}:
        agent = db.get(Agent, task.target_id) if task.target_id else None
        if agent and agent.status == "abnormal":
            agent.status = "running"


def close_related_inspection_items(db: Session, diagnosis: DiagnosisTicket) -> int:
    items = db.execute(
        select(InspectionItem).where(
            InspectionItem.object_type == diagnosis.object_type,
            InspectionItem.object_id == diagnosis.object_id,
            InspectionItem.status.in_(["failed", "warning"]),
        )
    ).scalars().all()
    touched_run_ids: set[str] = set()
    for item in items:
        item.status = "passed"
        item.detail = ((item.detail or "") + "\n已通过诊断一键修复验证。").strip()
        touched_run_ids.add(item.run_id)
    for run_id in touched_run_ids:
        recompute_inspection_run_status(db, run_id)
    return len(items)


def recompute_inspection_run_status(db: Session, run_id: str) -> None:
    run = db.get(InspectionRun, run_id)
    if not run:
        return
    items = db.execute(select(InspectionItem).where(InspectionItem.run_id == run_id).order_by(InspectionItem.created_at.asc())).scalars().all()
    failed_count = len([item for item in items if item.status == "failed"])
    warning_count = len([item for item in items if item.status == "warning"])
    passed_count = len([item for item in items if item.status == "passed"])
    run.status = "failed" if failed_count else ("warning" if warning_count else "success")
    run.pass_rate = passed_count / len(items) if items else 1
    run.summary = {
        "passed": passed_count,
        "warning": warning_count,
        "failed": failed_count,
        "items": [inspection_item_dto(item) for item in items],
        "lastFixVerifiedAt": _iso(now_utc()),
    }


def create_self_heal_approval(db: Session, payload: dict[str, Any], auth: Principal) -> ApprovalRequest:
    approval = ApprovalRequest(
        id=new_id("apr"),
        type="self_heal_task",
        risk_level=payload.get("riskLevel", "high"),
        applicant_id=auth.user.id,
        status="pending",
        reason=payload.get("reason"),
        payload_snapshot=payload,
    )
    db.add(approval)
    db.flush()
    ensure_approval_step(db, approval)
    audit(db, auth.user.id, "ops", "request_approval", "approval", approval.id, after=payload)
    return approval


def fix_task_dto(task: FixTask) -> dict[str, Any]:
    return {
        "id": task.id,
        "diagnosisId": task.diagnosis_id,
        "selfHealTaskId": task.self_heal_task_id,
        "taskType": task.task_type,
        "targetType": task.target_type,
        "targetId": task.target_id,
        "status": task.status,
        "result": task.result,
        "operatorId": task.operator_id,
        "startedAt": _iso(task.started_at),
        "endedAt": _iso(task.ended_at),
        "createdAt": _iso(task.created_at),
    }


@router.post("/diagnostics/{diagnosis_id}/fix")
def fix_diagnosis(diagnosis_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("ops:manage"))], payload: dict[str, Any] = Body(default_factory=dict)):
    item = db.get(DiagnosisTicket, diagnosis_id)
    if not item:
        raise BusinessError(400001, "invalid request", 404)
    task_payload = {
        "taskType": payload.get("taskType", "restart_agent" if item.object_type == "agent" else "cache_refresh"),
        "targetType": item.object_type,
        "targetId": item.object_id,
        "diagnosisId": diagnosis_id,
        "riskLevel": payload.get("riskLevel", "normal"),
    } | {k: v for k, v in payload.items() if k in {"forceFail", "errorMessage"}}
    task = create_self_heal_task(db, task_payload, auth.user.id)
    fix_task = FixTask(
        id=new_id("fix"),
        diagnosis_id=diagnosis_id,
        self_heal_task_id=task.id,
        task_type=task.task_type,
        target_type=task.target_type,
        target_id=task.target_id,
        status=task.status,
        result=task.result,
        operator_id=auth.user.id,
        started_at=task.started_at,
        ended_at=task.ended_at,
    )
    db.add(fix_task)
    audit(
        db,
        auth.user.id,
        "diagnosis",
        "fix",
        "diagnosis",
        diagnosis_id,
        after={
            "fixTaskId": fix_task.id,
            "selfHealTaskId": task.id,
            "closedAlertCount": (task.result or {}).get("closedAlertCount", 0),
            "updatedInspectionItemCount": (task.result or {}).get("updatedInspectionItemCount", 0),
        },
    )
    db.commit()
    return success(
        {
            "fixTaskId": fix_task.id,
            "selfHealTaskId": task.id,
            "status": task.status,
            "closedAlertCount": (task.result or {}).get("closedAlertCount", 0),
            "updatedInspectionItemCount": (task.result or {}).get("updatedInspectionItemCount", 0),
        },
        request.state.request_id,
    )


@router.get("/ops-tasks")
def list_ops_tasks(db: Db, request: Request, auth: Auth, status: str | None = None, taskType: str | None = None, targetType: str | None = None, page: int = 1, pageSize: int = 20):
    stmt = select(SelfHealTask)
    if status:
        stmt = stmt.where(SelfHealTask.status == status)
    if taskType:
        stmt = stmt.where(SelfHealTask.task_type == taskType)
    if targetType:
        stmt = stmt.where(SelfHealTask.target_type == targetType)
    rows = db.execute(stmt.order_by(SelfHealTask.created_at.desc())).scalars().all()
    return success(paginate([self_heal_task_dto(t) for t in rows], page, pageSize), request.state.request_id)


@router.post("/ops-tasks")
def create_ops_task(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("ops:manage"))], payload: dict[str, Any] = Body(...)):
    task_type = payload.get("taskType", "restart_agent")
    risk_level = payload.get("riskLevel", "high" if task_type in HIGH_RISK_OPS_TASK_TYPES else "normal")
    task_payload = payload | {"taskType": task_type, "riskLevel": risk_level}
    if risk_level in {"high", "critical"} and not payload.get("approvalId"):
        approval = create_self_heal_approval(db, task_payload, auth)
        db.commit()
        return success({"status": "pending_approval", "approvalId": approval.id, "riskLevel": approval.risk_level}, request.state.request_id)
    approval_id = payload.get("approvalId")
    if approval_id:
        approval = db.get(ApprovalRequest, approval_id)
        if not approval or approval.type != "self_heal_task":
            raise BusinessError(400001, "invalid request", 404, {"field": "approvalId"})
        if approval.status != "approved":
            raise BusinessError(APPROVAL_REQUIRED, "approval required", 409, {"approvalId": approval.id, "status": approval.status})
        existing = db.execute(select(SelfHealTask).where(SelfHealTask.approval_id == approval.id)).scalar_one_or_none()
        if existing:
            return success(self_heal_task_dto(existing), request.state.request_id)
        task_payload = dict(approval.payload_snapshot or {})
    task = create_self_heal_task(db, task_payload, auth.user.id, approval_id)
    audit(db, auth.user.id, "ops", "create_task", "self_heal_task", task.id, after=self_heal_task_dto(task))
    db.commit()
    return success(self_heal_task_dto(task), request.state.request_id)


@router.get("/ops-tasks/{task_id}")
def ops_task_detail(task_id: str, db: Db, request: Request, auth: Auth):
    task = db.get(SelfHealTask, task_id)
    if not task:
        raise BusinessError(400001, "invalid request", 404)
    return success(self_heal_task_dto(task), request.state.request_id)


@router.get("/inspection-tasks")
def inspection_tasks(db: Db, request: Request, auth: Auth):
    return success([{"id": t.id, "name": t.name, "scope": t.scope, "status": t.status} for t in db.execute(select(InspectionTask)).scalars().all()], request.state.request_id)


@router.post("/inspection-tasks")
def create_inspection_task(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("ops:manage"))], payload: dict[str, Any] = Body(...)):
    task = InspectionTask(id=new_id("ins"), name=payload.get("name", "全域巡检"), scope=payload.get("scope", {}), status="enabled")
    db.add(task)
    audit(db, auth.user.id, "inspection", "create_task", "inspection_task", task.id, after={"name": task.name, "scope": task.scope, "status": task.status})
    db.commit()
    return success({"id": task.id, "status": task.status}, request.state.request_id)


@router.post("/inspection-tasks/{task_id}/run")
def run_inspection(task_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("ops:manage"))], payload: dict[str, Any] = Body(default_factory=dict)):
    task = db.get(InspectionTask, task_id)
    if not task:
        raise BusinessError(400001, "invalid request", 404)
    items = payload.get("items") or default_inspection_items()
    failed_items = [item for item in items if item.get("status") == "failed"]
    warning_items = [item for item in items if item.get("status") == "warning"]
    abnormal_items = failed_items + warning_items
    passed_count = len(items) - len(abnormal_items)
    pass_rate = passed_count / len(items) if items else 1
    status = "failed" if failed_items else ("warning" if warning_items else "success")
    run = InspectionRun(
        id=new_id("run"),
        task_id=task_id,
        status=status,
        pass_rate=pass_rate,
        summary={"passed": passed_count, "warning": len(warning_items), "failed": len(failed_items), "items": items},
        ended_at=now_utc(),
    )
    db.add(run)
    inspection_items: list[InspectionItem] = []
    for item in items:
        row = InspectionItem(
            id=new_id("ini"),
            run_id=run.id,
            name=item.get("name", "inspection_item"),
            status=item.get("status", "passed"),
            level=item.get("level"),
            object_type=item.get("objectType"),
            object_id=item.get("objectId"),
            error_code=item.get("errorCode"),
            detail=item.get("detail"),
            root_cause=item.get("rootCause"),
            suggestion=item.get("suggestion"),
        )
        inspection_items.append(row)
        db.add(row)
    for item in abnormal_items:
        alert = Alert(
            id=new_id("alt"),
            level=item.get("level", "P1"),
            status="pending",
            source_type=item.get("objectType", "inspection"),
            source_id=item.get("objectId", run.id),
            category="inspection",
            error_code=item.get("errorCode", "INSPECTION_FAILED"),
            title=item.get("name", "巡检项失败"),
            detail=item.get("detail"),
            root_cause=item.get("rootCause"),
            suggestion=item.get("suggestion", "请按巡检报告处理"),
        )
        db.add(alert)
        if alert.level in {"P0", "P1"}:
            db.add(
                DiagnosisTicket(
                    id=new_id("diag"),
                    level=alert.level,
                    object_type=alert.source_type,
                    object_id=alert.source_id,
                    status="open",
                    summary=alert.title,
                    root_cause=alert.root_cause,
                    suggestion=alert.suggestion,
                )
            )
    audit(db, auth.user.id, "inspection", "run", "inspection_run", run.id)
    db.commit()
    return success({"runId": run.id, "status": run.status}, request.state.request_id)


def default_inspection_items() -> list[dict[str, Any]]:
    return [
        {"name": "server", "status": "passed", "objectType": "server", "objectId": "default", "suggestion": "Keep OS patches and resource limits under regular review."},
        {"name": "network", "status": "passed", "objectType": "network", "objectId": "default", "suggestion": "Verify private network reachability and DNS resolution."},
        {"name": "container", "status": "passed", "objectType": "container", "objectId": "runtime", "suggestion": "Review container restart count and resource pressure."},
        {"name": "agent", "status": "passed", "objectType": "agent", "objectId": "all", "suggestion": "Check abnormal instances and pending deployment tasks."},
        {"name": "model_gateway", "status": "warning", "level": "P1", "objectType": "model", "objectId": "m001", "errorCode": "MODEL_GATEWAY_CHECK", "rootCause": "Model gateway probe requires operator confirmation.", "suggestion": "Probe enabled models and validate route fallback policy."},
        {"name": "storage", "status": "passed", "objectType": "storage", "objectId": "default", "suggestion": "Review storage capacity and cleanup old artifacts."},
        {"name": "database", "status": "passed", "objectType": "database", "objectId": "default", "suggestion": "Check backup freshness and slow query trend."},
        {"name": "message_channel", "status": "passed", "objectType": "channel", "objectId": "all", "suggestion": "Reconnect disabled channels and validate webhook credentials."},
        {"name": "certificate", "status": "passed", "objectType": "certificate", "objectId": "default", "suggestion": "Track certificate expiry and renewal owner."},
        {"name": "backup_task", "status": "passed", "objectType": "backup", "objectId": "all", "suggestion": "Verify recent backup tasks and restore drills."},
    ]


def inspection_item_dto(item: InspectionItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "runId": item.run_id,
        "name": item.name,
        "status": item.status,
        "level": item.level,
        "objectType": item.object_type,
        "objectId": item.object_id,
        "errorCode": item.error_code,
        "detail": item.detail,
        "rootCause": item.root_cause,
        "suggestion": item.suggestion,
        "createdAt": _iso(item.created_at),
    }


def inspection_run_dto(run: InspectionRun, items: list[InspectionItem]) -> dict[str, Any]:
    stats = {
        "total": len(items),
        "passed": len([item for item in items if item.status == "passed"]),
        "warning": len([item for item in items if item.status == "warning"]),
        "failed": len([item for item in items if item.status == "failed"]),
    }
    return {
        "id": run.id,
        "taskId": run.task_id,
        "status": run.status,
        "passRate": run.pass_rate,
        "summary": run.summary,
        "stats": stats,
        "items": [inspection_item_dto(item) for item in items],
        "startedAt": _iso(run.started_at),
        "endedAt": _iso(run.ended_at),
    }


@router.get("/inspection-runs/{run_id}")
def inspection_run(run_id: str, db: Db, request: Request, auth: Auth):
    run = db.get(InspectionRun, run_id)
    if not run:
        raise BusinessError(400001, "invalid request", 404)
    items = db.execute(select(InspectionItem).where(InspectionItem.run_id == run_id).order_by(InspectionItem.created_at.asc())).scalars().all()
    return success(inspection_run_dto(run, items), request.state.request_id)


@router.get("/inspection-runs/{run_id}/export")
def inspection_export(run_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("ops:manage"))], format: str = "excel"):
    run = db.get(InspectionRun, run_id)
    if not run:
        raise BusinessError(400001, "invalid request", 404)
    if format not in {"html", "pdf", "excel"}:
        raise BusinessError(400001, "invalid request", 422, {"field": "format"})
    items = db.execute(select(InspectionItem).where(InspectionItem.run_id == run_id).order_by(InspectionItem.created_at.asc())).scalars().all()
    report = inspection_run_dto(run, items)
    task = create_export_task(db, auth, "inspection", {"runId": run_id, "status": run.status, "stats": report["stats"], "format": format})
    extension = {"excel": "xlsx", "html": "html", "pdf": "pdf"}[format]
    task.file_url = task.file_url.rsplit(".", 1)[0] + f".{extension}"
    db.commit()
    return success({"taskId": task.id, "status": task.status, "downloadUrl": task.file_url, "watermark": task.watermark, "format": format, "report": report}, request.state.request_id)


@router.get("/cost/overview")
@router.get("/cost/by-department")
@router.get("/cost/by-project")
@router.get("/cost/by-model")
@router.get("/cost/by-agent")
@router.get("/cost/by-resource-package")
def cost(
    db: Db,
    request: Request,
    auth: Auth,
    startDate: str | None = None,
    endDate: str | None = None,
    departmentId: str | None = None,
    projectId: str | None = None,
    period: str | None = None,
):
    path = request.url.path.rsplit("/", 1)[-1]
    dimension_map = {"by-department": "department", "by-project": "project", "by-model": "model", "by-agent": "agent", "by-resource-package": "resource_package"}
    stmt = select(CostDailyStat)
    if path in dimension_map:
        stmt = stmt.where(CostDailyStat.dimension_type == dimension_map[path])
    if startDate:
        stmt = stmt.where(CostDailyStat.date >= date.fromisoformat(startDate))
    if endDate:
        stmt = stmt.where(CostDailyStat.date <= date.fromisoformat(endDate))
    if departmentId:
        stmt = stmt.where(CostDailyStat.dimension_type == "department", CostDailyStat.dimension_id == departmentId)
    if projectId:
        stmt = stmt.where(CostDailyStat.dimension_type == "project", CostDailyStat.dimension_id == projectId)
    rows = db.execute(stmt).scalars().all()
    if not rows:
        return success({"items": [], "totalCost": 0, "period": period or "all"}, request.state.request_id)
    items = aggregate_cost_rows(rows, period)
    return success({"items": items, "totalCost": round(sum(item["totalCost"] for item in items), 4), "period": period or "all"}, request.state.request_id)


@router.get("/cost/export")
def cost_export(
    db: Db,
    request: Request,
    auth: Annotated[Principal, Depends(require_permission("security:manage"))],
    dimension: str | None = None,
    startDate: str | None = None,
    endDate: str | None = None,
    departmentId: str | None = None,
    projectId: str | None = None,
    period: str | None = None,
):
    stmt = select(CostDailyStat)
    if dimension:
        dimension_type = {"department": "department", "project": "project", "model": "model", "agent": "agent", "resource_package": "resource_package"}.get(dimension, dimension)
        stmt = stmt.where(CostDailyStat.dimension_type == dimension_type)
    if startDate:
        stmt = stmt.where(CostDailyStat.date >= date.fromisoformat(startDate))
    if endDate:
        stmt = stmt.where(CostDailyStat.date <= date.fromisoformat(endDate))
    if departmentId:
        stmt = stmt.where(CostDailyStat.dimension_type == "department", CostDailyStat.dimension_id == departmentId)
    if projectId:
        stmt = stmt.where(CostDailyStat.dimension_type == "project", CostDailyStat.dimension_id == projectId)
    rows = db.execute(stmt).scalars().all()
    report = {
        "items": aggregate_cost_rows(rows, period),
        "period": period or "all",
        "dimension": dimension,
        "startDate": startDate,
        "endDate": endDate,
        "departmentId": departmentId,
        "projectId": projectId,
    }
    report["totalCost"] = round(sum(item["totalCost"] for item in report["items"]), 4)
    task = create_export_task(
        db,
        auth,
        "cost",
        {
            "dimension": dimension,
            "startDate": startDate,
            "endDate": endDate,
            "departmentId": departmentId,
            "projectId": projectId,
            "period": period,
            "totalCost": report["totalCost"],
        },
    )
    db.commit()
    return success({"taskId": task.id, "status": task.status, "downloadUrl": task.file_url, "watermark": task.watermark, "query": task.query_snapshot, "report": report}, request.state.request_id)


def aggregate_cost_rows(rows: list[CostDailyStat], period: str | None = None) -> list[dict[str, Any]]:
    if period and period not in {"day", "week", "month", "quarter"}:
        raise BusinessError(400001, "invalid request", 422, {"field": "period"})
    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        bucket = cost_period_bucket(row.date, period)
        key = (row.dimension_type, row.dimension_id, bucket.get("periodStart"))
        item = grouped.setdefault(
            key,
            {
                "dimensionType": row.dimension_type,
                "dimensionId": row.dimension_id,
                "dimensionName": row.dimension_name,
                "callCount": 0,
                "tokens": 0,
                "modelCost": 0.0,
                "containerCost": 0.0,
                "seatCost": 0.0,
                "totalCost": 0.0,
            }
            | bucket,
        )
        item["callCount"] += row.call_count
        item["tokens"] += row.tokens
        item["modelCost"] += row.model_cost
        item["containerCost"] += row.container_cost
        item["seatCost"] += row.seat_cost
        item["totalCost"] += row.total_cost
    return [
        item
        | {
            "modelCost": round(item["modelCost"], 4),
            "containerCost": round(item["containerCost"], 4),
            "seatCost": round(item["seatCost"], 4),
            "totalCost": round(item["totalCost"], 4),
        }
        for item in sorted(grouped.values(), key=lambda value: (value.get("periodStart") or "", value["dimensionType"], value["dimensionId"]))
    ]


def cost_period_bucket(value: date, period: str | None) -> dict[str, Any]:
    if not period:
        return {}
    if period == "day":
        return {"period": "day", "periodStart": value.isoformat(), "periodEnd": value.isoformat()}
    if period == "week":
        start = value - timedelta(days=value.weekday())
        end = start + timedelta(days=6)
        return {"period": "week", "periodStart": start.isoformat(), "periodEnd": end.isoformat()}
    if period == "month":
        start = value.replace(day=1)
        next_month = date(value.year + (1 if value.month == 12 else 0), 1 if value.month == 12 else value.month + 1, 1)
        end = next_month - timedelta(days=1)
        return {"period": "month", "periodStart": start.isoformat(), "periodEnd": end.isoformat()}
    quarter_month = ((value.month - 1) // 3) * 3 + 1
    start = date(value.year, quarter_month, 1)
    next_quarter_month = quarter_month + 3
    next_quarter = date(value.year + (1 if next_quarter_month > 12 else 0), next_quarter_month - 12 if next_quarter_month > 12 else next_quarter_month, 1)
    end = next_quarter - timedelta(days=1)
    return {"period": "quarter", "periodStart": start.isoformat(), "periodEnd": end.isoformat()}


def resource_package_dto(package: ResourcePackage) -> dict[str, Any]:
    return {
        "id": package.id,
        "name": package.name,
        "packageType": package.package_type,
        "targetType": package.target_type,
        "targetId": package.target_id,
        "cpu": float(package.cpu or 0),
        "memoryGb": float(package.memory_gb or 0),
        "gpu": float(package.gpu or 0),
        "storageGb": float(package.storage_gb or 0),
        "fixedDailyCost": float(package.fixed_daily_cost or 0),
        "status": package.status,
        "createdAt": _iso(package.created_at),
        "updatedAt": _iso(package.updated_at),
    }


@router.get("/resource-packages")
def list_resource_packages(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("security:manage"))], targetType: str | None = None, targetId: str | None = None, status: str | None = None, page: int = 1, pageSize: int = 20):
    stmt = select(ResourcePackage)
    if targetType:
        stmt = stmt.where(ResourcePackage.target_type == targetType)
    if targetId:
        stmt = stmt.where(ResourcePackage.target_id == targetId)
    if status:
        stmt = stmt.where(ResourcePackage.status == status)
    rows = db.execute(stmt.order_by(ResourcePackage.created_at.desc())).scalars().all()
    return success(paginate([resource_package_dto(p) for p in rows], page, pageSize), request.state.request_id)


@router.post("/resource-packages")
def create_resource_package(payload: ResourcePackageRequest, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("security:manage"))]):
    package = ResourcePackage(
        id=new_id("rp"),
        name=payload.name,
        package_type=payload.packageType,
        target_type=payload.targetType,
        target_id=payload.targetId,
        cpu=payload.cpu,
        memory_gb=payload.memoryGb,
        gpu=payload.gpu,
        storage_gb=payload.storageGb,
        fixed_daily_cost=payload.fixedDailyCost,
        status=payload.status,
    )
    db.add(package)
    audit(db, auth.user.id, "cost", "create_resource_package", "resource_package", package.id, after=resource_package_dto(package))
    db.commit()
    return success(resource_package_dto(package), request.state.request_id)


@router.put("/resource-packages/{package_id}")
def update_resource_package(package_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("security:manage"))], payload: dict[str, Any] = Body(...)):
    package = db.get(ResourcePackage, package_id)
    if not package:
        raise BusinessError(400001, "invalid request", 404)
    before = resource_package_dto(package)
    field_map = {
        "name": "name",
        "packageType": "package_type",
        "targetType": "target_type",
        "targetId": "target_id",
        "cpu": "cpu",
        "memoryGb": "memory_gb",
        "gpu": "gpu",
        "storageGb": "storage_gb",
        "fixedDailyCost": "fixed_daily_cost",
        "status": "status",
    }
    for api_field, model_field in field_map.items():
        if api_field in payload:
            setattr(package, model_field, payload[api_field])
    package.updated_at = now_utc()
    audit(db, auth.user.id, "cost", "update_resource_package", "resource_package", package.id, before=before, after=resource_package_dto(package))
    db.commit()
    return success(resource_package_dto(package), request.state.request_id)


def cost_rule_dto(rule: CostRule) -> dict[str, Any]:
    return {
        "id": rule.id,
        "name": rule.name,
        "ruleType": rule.rule_type,
        "scopeType": rule.scope_type,
        "scopeId": rule.scope_id,
        "threshold": rule.threshold,
        "level": rule.level,
        "status": rule.status,
        "config": rule.config,
        "createdAt": _iso(rule.created_at),
        "updatedAt": _iso(rule.updated_at),
    }


def budget_dto(budget: Budget) -> dict[str, Any]:
    used_amount = float(budget.used_amount or 0)
    limit_amount = float(budget.limit_amount or 0)
    usage_ratio = (used_amount / limit_amount) if limit_amount else 0
    return {
        "id": budget.id,
        "name": budget.name,
        "scopeType": budget.scope_type,
        "scopeId": budget.scope_id,
        "period": budget.period,
        "limitAmount": limit_amount,
        "usedAmount": used_amount,
        "thresholdRatio": budget.threshold_ratio,
        "usageRatio": round(usage_ratio, 4),
        "status": budget.status,
        "ownerId": budget.owner_id,
        "createdAt": _iso(budget.created_at),
        "updatedAt": _iso(budget.updated_at),
    }


def budget_usage_from_stats(db: Session, budget: Budget) -> float:
    amount = db.scalar(
        select(func.sum(CostDailyStat.total_cost)).where(
            CostDailyStat.dimension_type == budget.scope_type,
            CostDailyStat.dimension_id == budget.scope_id,
        )
    )
    return float(amount or 0)


def open_budget_alert(db: Session, budget: Budget, error_code: str) -> Alert | None:
    return db.execute(
        select(Alert).where(
            Alert.source_type == "budget",
            Alert.source_id == budget.id,
            Alert.error_code == error_code,
            Alert.status.in_(["pending", "processing", "suspended"]),
        )
    ).scalar_one_or_none()


def create_budget_alert(db: Session, budget: Budget, error_code: str, level: str, usage_ratio: float) -> Alert:
    existing = open_budget_alert(db, budget, error_code)
    if existing:
        existing.detail = f"Budget {budget.name} usage ratio is {usage_ratio:.2%}."
        existing.updated_at = now_utc()
        return existing
    alert = Alert(
        id=new_id("alt"),
        level=level,
        status="pending",
        source_type="budget",
        source_id=budget.id,
        category="cost",
        error_code=error_code,
        title=f"Cost budget alert: {budget.name}",
        detail=f"Budget {budget.name} usage ratio is {usage_ratio:.2%}.",
        root_cause="Cost consumption reached the configured budget threshold.",
        suggestion="Review high cost departments, models, agents, and adjust usage or budget.",
        owner_id=budget.owner_id,
    )
    db.add(alert)
    return alert


@router.get("/cost-rules")
def list_cost_rules(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("security:manage"))], ruleType: str | None = None, status: str | None = None, page: int = 1, pageSize: int = 20):
    stmt = select(CostRule)
    if ruleType:
        stmt = stmt.where(CostRule.rule_type == ruleType)
    if status:
        stmt = stmt.where(CostRule.status == status)
    rows = db.execute(stmt.order_by(CostRule.created_at.desc())).scalars().all()
    return success(paginate([cost_rule_dto(r) for r in rows], page, pageSize), request.state.request_id)


@router.post("/cost-rules")
def create_cost_rule(payload: CostRuleRequest, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("security:manage"))]):
    rule = CostRule(
        id=new_id("cr"),
        name=payload.name,
        rule_type=payload.ruleType,
        scope_type=payload.scopeType,
        scope_id=payload.scopeId,
        threshold=payload.threshold,
        level=payload.level,
        status=payload.status,
        config=payload.config,
    )
    db.add(rule)
    audit(db, auth.user.id, "cost", "create_rule", "cost_rule", rule.id, after=cost_rule_dto(rule))
    db.commit()
    return success(cost_rule_dto(rule), request.state.request_id)


@router.get("/budgets")
def list_budgets(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("security:manage"))], scopeType: str | None = None, scopeId: str | None = None, status: str | None = None, page: int = 1, pageSize: int = 20):
    stmt = select(Budget)
    if scopeType:
        stmt = stmt.where(Budget.scope_type == scopeType)
    if scopeId:
        stmt = stmt.where(Budget.scope_id == scopeId)
    if status:
        stmt = stmt.where(Budget.status == status)
    rows = db.execute(stmt.order_by(Budget.created_at.desc())).scalars().all()
    return success(paginate([budget_dto(b) for b in rows], page, pageSize), request.state.request_id)


@router.post("/budgets")
def create_budget(payload: BudgetRequest, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("security:manage"))]):
    budget = Budget(
        id=new_id("bdg"),
        name=payload.name,
        scope_type=payload.scopeType,
        scope_id=payload.scopeId,
        period=payload.period,
        limit_amount=payload.limitAmount,
        used_amount=0,
        threshold_ratio=payload.thresholdRatio,
        status=payload.status,
        owner_id=payload.ownerId,
    )
    db.add(budget)
    audit(db, auth.user.id, "cost", "create_budget", "budget", budget.id, after=budget_dto(budget))
    db.commit()
    return success(budget_dto(budget), request.state.request_id)


@router.put("/budgets/{budget_id}")
def update_budget(budget_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("security:manage"))], payload: dict[str, Any] = Body(...)):
    budget = db.get(Budget, budget_id)
    if not budget:
        raise BusinessError(400001, "invalid request", 404)
    before = budget_dto(budget)
    field_map = {
        "name": "name",
        "scopeType": "scope_type",
        "scopeId": "scope_id",
        "period": "period",
        "limitAmount": "limit_amount",
        "thresholdRatio": "threshold_ratio",
        "status": "status",
        "ownerId": "owner_id",
    }
    for api_field, model_field in field_map.items():
        if api_field in payload:
            setattr(budget, model_field, payload[api_field])
    budget.updated_at = now_utc()
    audit(db, auth.user.id, "cost", "update_budget", "budget", budget.id, before=before, after=budget_dto(budget))
    db.commit()
    return success(budget_dto(budget), request.state.request_id)


@router.post("/budgets/{budget_id}/evaluate")
def evaluate_budget(budget_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("security:manage"))], payload: dict[str, Any] = Body(default_factory=dict)):
    budget = db.get(Budget, budget_id)
    if not budget:
        raise BusinessError(400001, "invalid request", 404)
    used_amount = float(payload["usedAmount"]) if "usedAmount" in payload else budget_usage_from_stats(db, budget)
    budget.used_amount = used_amount
    budget.updated_at = now_utc()
    usage_ratio = (budget.used_amount / budget.limit_amount) if budget.limit_amount else 0
    evaluation_status = "ok"
    alert = None
    alert_level = None
    if budget.status == "active" and budget.limit_amount > 0 and usage_ratio >= 1:
        alert_level = "P1"
        alert = create_budget_alert(db, budget, "BUDGET_EXCEEDED", alert_level, usage_ratio)
        evaluation_status = "over_limit"
    elif budget.status == "active" and budget.limit_amount > 0 and usage_ratio >= budget.threshold_ratio:
        alert_level = "P2"
        alert = create_budget_alert(db, budget, "BUDGET_THRESHOLD", alert_level, usage_ratio)
        evaluation_status = "warning"
    audit(
        db,
        auth.user.id,
        "cost",
        "budget_evaluate",
        "budget",
        budget.id,
        after={"usedAmount": budget.used_amount, "usageRatio": round(usage_ratio, 4), "status": evaluation_status, "alertId": alert.id if alert else None},
    )
    db.commit()
    return success(
        budget_dto(budget) | {"evaluationStatus": evaluation_status, "alertId": alert.id if alert else None, "alertLevel": alert_level},
        request.state.request_id,
    )


@router.get("/audit/operation-logs")
def operation_logs(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("audit:view"))], page: int = 1, pageSize: int = 20, module: str | None = None, actorId: str | None = None, action: str | None = None, startTime: str | None = None, endTime: str | None = None):
    integrity_by_id = audit_integrity_map(db)
    stmt = select(AuditLog)
    if module:
        stmt = stmt.where(AuditLog.module == module)
    if actorId:
        stmt = stmt.where(AuditLog.actor_id == actorId)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if start := _parse_dt(startTime):
        stmt = stmt.where(AuditLog.created_at >= start)
    if end := _parse_dt(endTime):
        stmt = stmt.where(AuditLog.created_at <= end)
    logs = db.execute(stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())).scalars().all()
    data = [audit_log_dto(row, integrity_by_id) for row in logs]
    return success(paginate(data, page, pageSize), request.state.request_id)


def audit_integrity_map(db: Session) -> dict[str, str]:
    all_logs = db.execute(select(AuditLog).order_by(AuditLog.created_at.asc(), AuditLog.id.asc())).scalars().all()
    integrity_by_id: dict[str, str] = {}
    rolling_hash = ""
    for row in all_logs:
        expected_hash = audit_hash_payload(
            hash_prev=row.hash_prev,
            actor_id=row.actor_id,
            module=row.module,
            action=row.action,
            object_type=row.object_type,
            object_id=row.object_id,
            result=row.result,
            error_message=row.error_message,
            before_value=row.before_value,
            after_value=row.after_value,
            created_at=row.created_at,
        )
        integrity_by_id[row.id] = "valid" if row.hash_prev == rolling_hash and row.hash_current == expected_hash else "tampered"
        rolling_hash = row.hash_current
    return integrity_by_id


def audit_log_dto(row: AuditLog, integrity_by_id: dict[str, str] | None = None) -> dict[str, Any]:
    integrity_by_id = integrity_by_id or {}
    return {
        "id": row.id,
        "actor": {"id": row.actor_id},
        "module": row.module,
        "action": row.action,
        "objectType": row.object_type,
        "objectId": row.object_id,
        "ip": row.ip,
        "result": row.result,
        "errorMessage": row.error_message,
        "createdAt": _iso(row.created_at),
        "hashPrev": row.hash_prev,
        "hashCurrent": row.hash_current,
        "integrityStatus": integrity_by_id.get(row.id, "unknown"),
    }


@router.get("/audit/login-logs")
def audit_login_logs(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("audit:view"))], page: int = 1, pageSize: int = 20, userId: str | None = None, status: str | None = None, startTime: str | None = None, endTime: str | None = None):
    stmt = select(LoginLog)
    if userId:
        stmt = stmt.where(LoginLog.user_id == userId)
    if status:
        stmt = stmt.where(LoginLog.result == status)
    if start := _parse_dt(startTime):
        stmt = stmt.where(LoginLog.created_at >= start)
    if end := _parse_dt(endTime):
        stmt = stmt.where(LoginLog.created_at <= end)
    logs = db.execute(stmt.order_by(LoginLog.created_at.desc())).scalars().all()
    return success(paginate([{"id": l.id, "username": l.username, "userId": l.user_id, "result": l.result, "failureReason": l.failure_reason, "createdAt": _iso(l.created_at)} for l in logs], page, pageSize), request.state.request_id)


def approved_export_query(db: Session, approval_id: str, expected_type: str) -> dict[str, Any]:
    approval = db.get(ApprovalRequest, approval_id)
    if not approval or approval.type != expected_type:
        raise BusinessError(400001, "invalid request", 404, {"field": "approvalId"})
    if approval.status != "approved":
        raise BusinessError(APPROVAL_REQUIRED, "approval required", 409, {"approvalId": approval.id, "status": approval.status})
    return dict((approval.payload_snapshot or {}).get("query") or {})


@router.get("/audit/export")
def audit_export(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("audit:export"))], approvalId: str | None = None):
    if not approvalId:
        query = {k: v for k, v in dict(request.query_params).items() if k != "approvalId"}
        approval = ApprovalRequest(
            id=new_id("apr"),
            type="audit_export",
            risk_level="high",
            applicant_id=auth.user.id,
            status="pending",
            reason="audit log export",
            payload_snapshot={"exportType": "audit", "query": query},
        )
        db.add(approval)
        db.flush()
        ensure_approval_step(db, approval)
        audit(db, auth.user.id, "export", "request_approval", "approval", approval.id, after=approval.payload_snapshot)
        db.commit()
        return success({"status": "pending_approval", "approvalId": approval.id, "payload": approval.payload_snapshot}, request.state.request_id)
    query = approved_export_query(db, approvalId, "audit_export")
    task = create_export_task(db, auth, "audit", query, approval_id=approvalId)
    db.commit()
    return success({"taskId": task.id, "status": task.status, "downloadUrl": task.file_url, "watermark": task.watermark, "approvalId": approvalId, "query": task.query_snapshot}, request.state.request_id)


def resolve_export_task(db: Session, export_key: str) -> ExportTask:
    task = db.get(ExportTask, export_key)
    if task:
        return task
    suffix = f"/{export_key}"
    task = db.execute(select(ExportTask).where(ExportTask.file_url.like(f"%{suffix}"))).scalars().first()
    if not task:
        raise BusinessError(400001, "invalid request", 404, {"field": "exportKey"})
    return task


def ensure_export_access(task: ExportTask, auth: Principal) -> None:
    if task.applicant_id == auth.user.id or "audit:export" in auth.permissions:
        return
    raise BusinessError(FORBIDDEN, "forbidden", 403)


@router.get("/exports")
def list_exports(
    db: Db,
    request: Request,
    auth: Auth,
    page: int = 1,
    pageSize: int = 20,
    type: str | None = None,
    status: str | None = None,
    applicantId: str | None = None,
):
    stmt = select(ExportTask)
    if type:
        stmt = stmt.where(ExportTask.type == type)
    if status:
        stmt = stmt.where(ExportTask.status == status)
    if applicantId:
        stmt = stmt.where(ExportTask.applicant_id == applicantId)
    if "audit:export" not in auth.permissions:
        stmt = stmt.where(ExportTask.applicant_id == auth.user.id)
    rows = db.execute(stmt.order_by(ExportTask.created_at.desc())).scalars().all()
    return success(paginate([export_task_dto(row) for row in rows], page, pageSize), request.state.request_id)


@router.get("/exports/{export_key}")
def get_export(export_key: str, db: Db, request: Request, auth: Auth):
    task = resolve_export_task(db, export_key)
    ensure_export_access(task, auth)
    return success(export_task_dto(task), request.state.request_id)


@router.get("/exports/{export_key}/download")
def download_export(export_key: str, db: Db, request: Request, auth: Auth):
    task = resolve_export_task(db, export_key)
    ensure_export_access(task, auth)
    record_sensitive_event(db, auth.user.id, "data_export_download", "download", "export_task", task.id, "high", detail={"exportType": task.type, "watermark": task.watermark})
    audit(db, auth.user.id, "export", "download", "export_task", task.id, after={"downloadUrl": task.file_url, "watermark": task.watermark})
    db.commit()
    return success(
        {
            **export_task_dto(task),
            "fileName": task.file_url.rsplit("/", 1)[-1],
            "contentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "content": f"mock export content for {task.type}; watermark={task.watermark}",
        },
        request.state.request_id,
    )


@router.get("/audit/sensitive-events")
def sensitive_events(
    db: Db,
    request: Request,
    auth: Annotated[Principal, Depends(require_permission("audit:view"))],
    page: int = 1,
    pageSize: int = 20,
    eventType: str | None = None,
    objectType: str | None = None,
    objectId: str | None = None,
    actorId: str | None = None,
    result: str | None = None,
):
    stmt = select(SensitiveEvent)
    if eventType:
        stmt = stmt.where(SensitiveEvent.event_type == eventType)
    if objectType:
        stmt = stmt.where(SensitiveEvent.object_type == objectType)
    if objectId:
        stmt = stmt.where(SensitiveEvent.object_id == objectId)
    if actorId:
        stmt = stmt.where(SensitiveEvent.actor_id == actorId)
    if result:
        stmt = stmt.where(SensitiveEvent.result == result)
    rows = db.execute(stmt.order_by(SensitiveEvent.created_at.desc())).scalars().all()
    return success(paginate([sensitive_event_dto(row) for row in rows], page, pageSize), request.state.request_id)


def security_policy_dto(policy: SecurityPolicy) -> dict[str, Any]:
    return {
        "id": policy.id,
        "name": policy.name,
        "category": policy.category,
        "status": policy.status,
        "riskLevel": policy.risk_level,
        "config": policy.config,
        "description": policy.description,
        "updatedAt": _iso(policy.updated_at),
    }


@router.get("/security-policies")
def security_policies(db: Db, request: Request, auth: Auth, category: str | None = None, status: str | None = None):
    stmt = select(SecurityPolicy)
    if category:
        stmt = stmt.where(SecurityPolicy.category == category)
    if status:
        stmt = stmt.where(SecurityPolicy.status == status)
    rows = db.execute(stmt.order_by(SecurityPolicy.category.asc(), SecurityPolicy.id.asc())).scalars().all()
    return success([security_policy_dto(policy) for policy in rows], request.state.request_id)


@router.get("/security-policies/{policy_id}")
def security_policy_detail(policy_id: str, db: Db, request: Request, auth: Auth):
    policy = db.get(SecurityPolicy, policy_id)
    if not policy:
        raise BusinessError(400001, "invalid request", 404)
    return success(security_policy_dto(policy), request.state.request_id)


def apply_security_policy_change(db: Session, approval: ApprovalRequest, actor_id: str | None) -> SecurityPolicy:
    snapshot = approval.payload_snapshot or {}
    policy = db.get(SecurityPolicy, snapshot.get("policyId"))
    if not policy:
        raise BusinessError(400001, "invalid request", 404, {"field": "policyId"})
    before = security_policy_dto(policy)
    policy.status = snapshot.get("status", policy.status)
    policy.config = snapshot.get("config", policy.config)
    policy.description = snapshot.get("description", policy.description)
    audit(db, actor_id, "security", "policy_change", "security_policy", policy.id, before=before, after=security_policy_dto(policy) | {"approvalId": approval.id})
    return policy


@router.put("/security-policies/{policy_id}")
def update_security_policy(policy_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("security:manage"))], payload: dict[str, Any] = Body(...)):
    policy = db.get(SecurityPolicy, policy_id)
    if not policy:
        raise BusinessError(400001, "invalid request", 404)
    snapshot = {
        "policyId": policy_id,
        "status": payload.get("status", policy.status),
        "config": payload.get("config", policy.config),
        "description": payload.get("description", policy.description),
    }
    high_risk_disable = policy.status == "enabled" and snapshot["status"] == "disabled"
    approval_id = payload.get("approvalId")
    if high_risk_disable and not approval_id:
        approval = ApprovalRequest(
            id=new_id("apr"),
            type="security_policy_change",
            risk_level="high",
            applicant_id=auth.user.id,
            status="pending",
            reason=payload.get("reason", "security policy change"),
            payload_snapshot=snapshot,
        )
        db.add(approval)
        db.flush()
        ensure_approval_step(db, approval)
        audit(db, auth.user.id, "security", "request_policy_change", "approval", approval.id, after=snapshot)
        db.commit()
        return success({"status": "pending_approval", "approvalId": approval.id, "payload": snapshot}, request.state.request_id)
    if approval_id:
        approval = db.get(ApprovalRequest, approval_id)
        if not approval or approval.type != "security_policy_change":
            raise BusinessError(400001, "invalid request", 404, {"field": "approvalId"})
        if approval.status != "approved":
            raise BusinessError(APPROVAL_REQUIRED, "approval required", 409, {"approvalId": approval.id, "status": approval.status})
        if (approval.payload_snapshot or {}).get("policyId") != policy_id:
            raise BusinessError(400001, "invalid request", 422, {"field": "approvalId"})
        policy = apply_security_policy_change(db, approval, auth.user.id)
    else:
        before = security_policy_dto(policy)
        policy.status = snapshot["status"]
        policy.config = snapshot["config"]
        policy.description = snapshot["description"]
        audit(db, auth.user.id, "security", "policy_change", "security_policy", policy.id, before=before, after=security_policy_dto(policy))
    db.commit()
    return success(security_policy_dto(policy), request.state.request_id)


@router.post("/approvals")
def create_approval(db: Db, request: Request, auth: Auth, payload: dict[str, Any] = Body(...)):
    item = ApprovalRequest(id=new_id("apr"), type=payload["type"], risk_level=payload.get("riskLevel", "high"), applicant_id=auth.user.id, status="pending", reason=payload.get("reason"), payload_snapshot=payload.get("payload", {}))
    db.add(item)
    db.flush()
    ensure_approval_step(db, item, payload.get("approverId"))
    create_notification(db, auth.user.id, "approval_pending", f"审批已提交：{item.type}", item.reason, "approval", item.id, {"riskLevel": item.risk_level})
    audit(db, auth.user.id, "approval", "create", "approval", item.id, after={"type": item.type, "riskLevel": item.risk_level, "status": item.status})
    db.commit()
    return success(approval_with_steps_dto(db, item), request.state.request_id)


@router.get("/approvals")
def approvals(db: Db, request: Request, auth: Auth, page: int = 1, pageSize: int = 20, status: str | None = None, type: str | None = None):
    stmt = select(ApprovalRequest)
    if status:
        stmt = stmt.where(ApprovalRequest.status == status)
    if type:
        stmt = stmt.where(ApprovalRequest.type == type)
    return success(paginate([approval_with_steps_dto(db, a) for a in db.execute(stmt).scalars().all()], page, pageSize), request.state.request_id)


def approval_dto(a: ApprovalRequest) -> dict[str, Any]:
    return {"id": a.id, "type": a.type, "riskLevel": a.risk_level, "applicantId": a.applicant_id, "status": a.status, "reason": a.reason, "payload": a.payload_snapshot, "createdAt": _iso(a.created_at)}


def approval_step_dto(step: ApprovalStep) -> dict[str, Any]:
    return {
        "id": step.id,
        "approvalId": step.approval_id,
        "stepNo": step.step_no,
        "approverId": step.approver_id,
        "decision": step.decision,
        "comment": step.comment,
        "decidedAt": _iso(step.decided_at),
    }


def approval_with_steps_dto(db: Session, approval: ApprovalRequest) -> dict[str, Any]:
    steps = db.execute(select(ApprovalStep).where(ApprovalStep.approval_id == approval.id).order_by(ApprovalStep.step_no.asc())).scalars().all()
    return approval_dto(approval) | {"steps": [approval_step_dto(step) for step in steps]}


def ensure_approval_step(db: Session, approval: ApprovalRequest, approver_id: str | None = None) -> ApprovalStep:
    step = db.execute(select(ApprovalStep).where(ApprovalStep.approval_id == approval.id, ApprovalStep.step_no == 1)).scalar_one_or_none()
    if step:
        return step
    step = ApprovalStep(approval_id=approval.id, step_no=1, approver_id=approver_id)
    db.add(step)
    return step


def apply_approval_snapshot_to_batch(db: Session, batch: BatchTask, approval: ApprovalRequest) -> None:
    snapshot = approval.payload_snapshot or {}
    targets = list(dict.fromkeys(snapshot.get("targetIds") or []))
    batch_type = snapshot.get("batchType") or batch.type
    batch.type = batch_type
    batch.scope_snapshot = {"targetIds": targets, "approvedSnapshot": snapshot}
    batch.total = len(targets)
    batch.success_count = 0
    batch.failed_count = 0
    batch.skipped_count = 0
    for item in db.execute(select(BatchTaskItem).where(BatchTaskItem.batch_task_id == batch.id)).scalars().all():
        db.delete(item)
    db.flush()
    for target_id in targets:
        db.add(BatchTaskItem(id=new_id("bti"), batch_task_id=batch.id, target_id=target_id, action=batch_type, status="queued"))


@router.get("/approvals/{approval_id}")
def approval_detail(approval_id: str, db: Db, request: Request, auth: Auth):
    item = db.get(ApprovalRequest, approval_id)
    if not item:
        raise BusinessError(400001, "invalid request", 404)
    return success(approval_with_steps_dto(db, item), request.state.request_id)


@router.post("/approvals/{approval_id}/approve")
@router.post("/approvals/{approval_id}/reject")
def approval_action(approval_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("approval:manage"))], payload: dict[str, Any] = Body(default_factory=dict)):
    action = request.url.path.rsplit("/", 1)[-1]
    item = db.get(ApprovalRequest, approval_id)
    if not item:
        raise BusinessError(400001, "invalid request", 404)
    item.status = "approved" if action == "approve" else "rejected"
    step = ensure_approval_step(db, item, auth.user.id)
    step.approver_id = payload.get("approverId", auth.user.id)
    step.decision = item.status
    step.comment = payload.get("comment")
    step.decided_at = now_utc()
    batch = db.execute(select(BatchTask).where(BatchTask.approval_id == approval_id)).scalar_one_or_none()
    if batch:
        if item.status == "approved":
            apply_approval_snapshot_to_batch(db, batch, item)
            batch.status = "queued"
        else:
            batch.status = "rejected"
    if item.type == "share_agent" and item.status == "approved":
        snapshot = item.payload_snapshot or {}
        exists = db.execute(
            select(ShareGrant).where(
                ShareGrant.agent_id == snapshot.get("agentId"),
                ShareGrant.scope_type == snapshot.get("scopeType"),
                ShareGrant.scope_id == snapshot.get("scopeId"),
                ShareGrant.permission == snapshot.get("permission", "use"),
                ShareGrant.status == "active",
            )
        ).scalar_one_or_none()
        if not exists:
            create_share_grant_from_payload(db, snapshot, auth.user.id)
    if item.type == "security_policy_change" and item.status == "approved":
        apply_security_policy_change(db, item, auth.user.id)
    if item.type == "model_secret_change" and item.status == "approved":
        apply_model_change_snapshot(db, item, auth.user.id)
    if item.type == "self_heal_task" and item.status == "approved":
        exists = db.execute(select(SelfHealTask).where(SelfHealTask.approval_id == item.id)).scalar_one_or_none()
        if not exists:
            create_self_heal_task(db, dict(item.payload_snapshot or {}), auth.user.id, item.id)
    if item.type == "memory_share":
        request_row = db.execute(select(MemoryShareRequest).where(MemoryShareRequest.approval_id == item.id)).scalar_one_or_none()
        if request_row:
            request_row.status = "approved" if item.status == "approved" else "rejected"
            request_row.decided_at = now_utc()
            if item.status == "approved":
                memory = db.get(Memory, request_row.memory_id)
                if memory:
                    memory.scope = request_row.target_scope
            audit(db, auth.user.id, "memory", item.status, "memory_share_request", request_row.id)
    create_notification(
        db,
        item.applicant_id,
        "approval_decided",
        f"审批已{item.status}：{item.type}",
        payload.get("comment") or item.reason,
        "approval",
        item.id,
        {"status": item.status, "decidedBy": auth.user.id},
    )
    audit(db, auth.user.id, "approval", action, "approval", item.id, after={"status": item.status, "step": approval_step_dto(step)})
    db.commit()
    return success(approval_with_steps_dto(db, item), request.state.request_id)


@router.get("/seat-packages")
def seat_packages(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("seat:manage"))]):
    return success([{"id": p.id, "name": p.name, "totalCount": p.total_count, "usedCount": p.used_count, "availableCount": p.total_count - p.used_count, "status": p.status, "expiresAt": _iso(p.expires_at)} for p in db.execute(select(SeatPackage)).scalars().all()], request.state.request_id)


@router.post("/seat-packages")
def create_seat_package(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("seat:manage"))], payload: dict[str, Any] = Body(...)):
    pkg = SeatPackage(id=new_id("seat_pkg"), name=payload["name"], total_count=payload.get("totalCount", 0), used_count=0, status="active", expires_at=_parse_dt(payload.get("expiresAt")))
    db.add(pkg)
    audit(db, auth.user.id, "seat", "create_package", "seat_package", pkg.id, after={"name": pkg.name, "totalCount": pkg.total_count, "status": pkg.status, "expiresAt": _iso(pkg.expires_at)})
    db.commit()
    return success({"id": pkg.id}, request.state.request_id)


@router.get("/seat-assignments")
def seat_assignments(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("seat:manage"))], departmentId: str | None = None, userId: str | None = None, agentId: str | None = None):
    stmt = select(SeatAssignment)
    if userId:
        stmt = stmt.where(SeatAssignment.assignee_id == userId)
    if agentId:
        stmt = stmt.where(SeatAssignment.agent_id == agentId)
    rows = db.execute(stmt).scalars().all()
    if departmentId:
        user_ids = set(db.execute(select(User.id).where(User.department_id == departmentId)).scalars().all())
        rows = [s for s in rows if s.assignee_id in user_ids]
    return success([seat_assignment_dto(s) for s in rows], request.state.request_id)


def seat_assignment_dto(s: SeatAssignment) -> dict[str, Any]:
    return {"id": s.id, "seatPackageId": s.seat_package_id, "assigneeType": s.assignee_type, "assigneeId": s.assignee_id, "agentId": s.agent_id, "status": s.status}


def seat_event_dto(row: SeatEvent) -> dict[str, Any]:
    return {
        "id": row.id,
        "seatPackageId": row.seat_package_id,
        "seatAssignmentId": row.seat_assignment_id,
        "eventType": row.event_type,
        "assigneeType": row.assignee_type,
        "assigneeId": row.assignee_id,
        "agentId": row.agent_id,
        "operatorId": row.operator_id,
        "before": row.before_value,
        "after": row.after_value,
        "reason": row.reason,
        "createdAt": _iso(row.created_at),
    }


def record_seat_event(
    db: Session,
    event_type: str,
    assignment: SeatAssignment | None,
    operator_id: str | None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason: str | None = None,
) -> SeatEvent:
    snapshot = after or before or {}
    row = SeatEvent(
        id=new_id("sev"),
        seat_package_id=(assignment.seat_package_id if assignment else snapshot.get("seatPackageId")),
        seat_assignment_id=(assignment.id if assignment else snapshot.get("id")),
        event_type=event_type,
        assignee_type=(assignment.assignee_type if assignment else snapshot.get("assigneeType")),
        assignee_id=(assignment.assignee_id if assignment else snapshot.get("assigneeId")),
        agent_id=(assignment.agent_id if assignment else snapshot.get("agentId")),
        operator_id=operator_id,
        before_value=before,
        after_value=after,
        reason=reason,
    )
    db.add(row)
    return row


@router.get("/seat-events")
def seat_events(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("seat:manage"))], page: int = 1, pageSize: int = 20, seatPackageId: str | None = None, assignmentId: str | None = None, eventType: str | None = None, assigneeId: str | None = None):
    stmt = select(SeatEvent)
    if seatPackageId:
        stmt = stmt.where(SeatEvent.seat_package_id == seatPackageId)
    if assignmentId:
        stmt = stmt.where(SeatEvent.seat_assignment_id == assignmentId)
    if eventType:
        stmt = stmt.where(SeatEvent.event_type == eventType)
    if assigneeId:
        stmt = stmt.where(SeatEvent.assignee_id == assigneeId)
    rows = db.execute(stmt.order_by(SeatEvent.created_at.desc())).scalars().all()
    return success(paginate([seat_event_dto(row) for row in rows], page, pageSize), request.state.request_id)


@router.post("/seat-assignments")
def create_seat_assignment(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("seat:manage"))], payload: dict[str, Any] = Body(...)):
    pkg = db.get(SeatPackage, payload["seatPackageId"])
    if not pkg or pkg.status != "active":
        raise BusinessError(400001, "invalid request", 422, {"field": "seatPackageId"})
    if pkg.total_count - pkg.used_count < 1:
        raise BusinessError(QUOTA_EXCEEDED, "quota exceeded", 422, {"required": 1, "available": max(pkg.total_count - pkg.used_count, 0), "seatPackageId": pkg.id})
    item = SeatAssignment(id=new_id("seat_asg"), seat_package_id=payload["seatPackageId"], assignee_type=payload["assigneeType"], assignee_id=payload["assigneeId"], agent_id=payload.get("agentId"), status="active")
    db.add(item)
    pkg.used_count += 1
    if item.assignee_type == "user":
        user = db.get(User, item.assignee_id)
        if user:
            user.seat_status = "assigned"
    after = seat_assignment_dto(item)
    record_seat_event(db, "assign", item, auth.user.id, after=after, reason=payload.get("reason"))
    audit(db, auth.user.id, "seat", "assign", "seat_assignment", item.id, after=after)
    db.commit()
    return success(after, request.state.request_id)


@router.delete("/seat-assignments/{assignment_id}")
def delete_seat_assignment(assignment_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("seat:manage"))]):
    item = db.get(SeatAssignment, assignment_id)
    if item:
        before = seat_assignment_dto(item)
        pkg = db.get(SeatPackage, item.seat_package_id)
        if item.status == "active" and pkg and pkg.used_count > 0:
            pkg.used_count -= 1
        if item.assignee_type == "user":
            user = db.get(User, item.assignee_id)
            if user:
                has_other_active = db.execute(
                    select(SeatAssignment.id).where(
                        SeatAssignment.assignee_type == "user",
                        SeatAssignment.assignee_id == user.id,
                        SeatAssignment.status == "active",
                        SeatAssignment.id != item.id,
                    )
                ).first()
                if not has_other_active:
                    user.seat_status = "unassigned"
        record_seat_event(db, "reclaim", item, auth.user.id, before=before, reason="assignment deleted")
        db.delete(item)
        audit(db, auth.user.id, "seat", "delete_assignment", "seat_assignment", assignment_id, before=before)
        db.commit()
    return success({}, request.state.request_id)


@router.post("/seat-assignments/{assignment_id}/transfer")
def transfer_seat(assignment_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("seat:manage"))], payload: dict[str, Any] = Body(...)):
    item = db.get(SeatAssignment, assignment_id)
    if not item:
        raise BusinessError(400001, "invalid request", 404)
    before = seat_assignment_dto(item)
    old_user = db.get(User, item.assignee_id) if item.assignee_type == "user" else None
    item.assignee_type = payload.get("assigneeType", item.assignee_type)
    item.assignee_id = payload.get("assigneeId", item.assignee_id)
    item.agent_id = payload.get("agentId", item.agent_id)
    item.status = payload.get("status", item.status)
    if old_user and old_user.id != item.assignee_id:
        has_other_active = db.execute(
            select(SeatAssignment.id).where(
                SeatAssignment.assignee_type == "user",
                SeatAssignment.assignee_id == old_user.id,
                SeatAssignment.status == "active",
                SeatAssignment.id != item.id,
            )
        ).first()
        if not has_other_active:
            old_user.seat_status = "unassigned"
    if item.assignee_type == "user" and item.status == "active":
        new_user = db.get(User, item.assignee_id)
        if new_user:
            new_user.seat_status = "assigned"
    after = seat_assignment_dto(item)
    record_seat_event(db, "transfer", item, auth.user.id, before=before, after=after, reason=payload.get("reason"))
    audit(db, auth.user.id, "seat", "transfer", "seat_assignment", assignment_id, before=before, after=after)
    db.commit()
    return success(after | {"transferReason": payload.get("reason")}, request.state.request_id)


def allocate_share_seat(db: Session, grant: ShareGrant, actor_id: str | None = None) -> SeatAssignment | None:
    if grant.scope_type != "user":
        return None
    pkg = db.execute(
        select(SeatPackage)
        .where(SeatPackage.status == "active", SeatPackage.total_count > SeatPackage.used_count)
        .order_by(SeatPackage.created_at.asc())
    ).scalars().first()
    if not pkg or pkg.total_count - pkg.used_count < 1:
        raise BusinessError(QUOTA_EXCEEDED, "quota exceeded", 422, {"required": 1, "available": max(pkg.total_count - pkg.used_count, 0) if pkg else 0, "seatPackageId": pkg.id if pkg else None})
    assignment = SeatAssignment(
        id=new_id("seat_asg"),
        seat_package_id=pkg.id,
        assignee_type="user",
        assignee_id=grant.scope_id,
        agent_id=grant.agent_id,
        status="active",
    )
    db.add(assignment)
    pkg.used_count += 1
    user = db.get(User, grant.scope_id)
    if user:
        user.seat_status = "assigned"
    record_seat_event(db, "share_assign", assignment, actor_id, after=seat_assignment_dto(assignment), reason=f"shareGrantId={grant.id}")
    return assignment


def create_share_grant_from_payload(db: Session, payload: dict[str, Any], actor_id: str | None) -> ShareGrant:
    permission = payload.get("permission", "use")
    if permission not in {"use", "view_config", "manage"}:
        raise BusinessError(400001, "invalid request", 422, {"field": "permission"})
    grant = ShareGrant(
        id=new_id("shr"),
        agent_id=payload["agentId"],
        scope_type=payload["scopeType"],
        scope_id=payload["scopeId"],
        permission=permission,
        expires_at=_parse_dt(payload.get("expiresAt")),
        reason=payload.get("reason"),
        status="active",
    )
    db.add(grant)
    db.flush()
    assignment = allocate_share_seat(db, grant, actor_id)
    audit(db, actor_id, "share", "create", "share_grant", grant.id, after=share_dto(grant) | {"seatAssignmentId": assignment.id if assignment else None})
    return grant


def reclaim_share_seats(db: Session, grant: ShareGrant, actor_id: str | None, reason: str) -> list[dict[str, Any]]:
    if grant.scope_type != "user":
        return []
    seats = db.execute(
        select(SeatAssignment).where(
            SeatAssignment.agent_id == grant.agent_id,
            SeatAssignment.assignee_type == "user",
            SeatAssignment.assignee_id == grant.scope_id,
            SeatAssignment.status == "active",
        )
    ).scalars().all()
    reclaimed = []
    for seat in seats[:1]:
        seat_before = seat_assignment_dto(seat)
        pkg = db.get(SeatPackage, seat.seat_package_id)
        if pkg and pkg.used_count > 0:
            pkg.used_count -= 1
        seat.status = "reclaimed"
        seat_after = seat_assignment_dto(seat)
        reclaimed.append(seat_after)
        record_seat_event(db, "share_reclaim", seat, actor_id, before=seat_before, after=seat_after, reason=reason)
        audit(db, actor_id, "seat", "reclaim", "seat_assignment", seat.id, before=seat_before, after=seat_after | {"reason": reason, "shareGrantId": grant.id})
    return reclaimed


def expire_share_grants_for_agent(db: Session, agent_id: str, actor_id: str | None) -> None:
    rows = db.execute(
        select(ShareGrant).where(
            ShareGrant.agent_id == agent_id,
            ShareGrant.status == "active",
            ShareGrant.expires_at.is_not(None),
            ShareGrant.expires_at <= now_utc(),
        )
    ).scalars().all()
    for grant in rows:
        before = share_dto(grant)
        reclaimed = reclaim_share_seats(db, grant, actor_id, "share expired")
        grant.status = "expired"
        audit(db, actor_id, "share", "expire", "share_grant", grant.id, before=before, after=share_dto(grant) | {"reclaimedSeats": reclaimed})


@router.post("/agents/{agent_id}/share-grants")
def create_share(agent_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("agent:share"))], payload: dict[str, Any] = Body(...)):
    if not scoped_agent(db, auth, agent_id):
        raise BusinessError(400001, "invalid request", 404)
    share_payload = {
        "agentId": agent_id,
        "scopeType": payload["scopeType"],
        "scopeId": payload["scopeId"],
        "permission": payload.get("permission", "use"),
        "expiresAt": payload.get("expiresAt"),
        "reason": payload.get("reason"),
    }
    if share_payload["scopeType"] in {"department", "project"} and not payload.get("approvalId"):
        approval = ApprovalRequest(
            id=new_id("apr"),
            type="share_agent",
            risk_level="high",
            applicant_id=auth.user.id,
            status="pending",
            reason=payload.get("reason"),
            payload_snapshot=share_payload,
        )
        db.add(approval)
        db.flush()
        ensure_approval_step(db, approval)
        audit(db, auth.user.id, "share", "request_approval", "approval", approval.id, after=share_payload)
        db.commit()
        return success({"status": "pending_approval", "approvalId": approval.id, "payload": share_payload}, request.state.request_id)
    grant = create_share_grant_from_payload(db, share_payload, auth.user.id)
    db.commit()
    return success(share_dto(grant), request.state.request_id)


@router.get("/agents/{agent_id}/share-grants")
def list_share(agent_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("agent:share"))]):
    if not scoped_agent(db, auth, agent_id):
        raise BusinessError(400001, "invalid request", 404)
    expire_share_grants_for_agent(db, agent_id, auth.user.id)
    db.commit()
    rows = db.execute(select(ShareGrant).where(ShareGrant.agent_id == agent_id)).scalars().all()
    return success([share_dto(g) for g in rows], request.state.request_id)


def share_dto(g: ShareGrant) -> dict[str, Any]:
    return {"id": g.id, "agentId": g.agent_id, "scopeType": g.scope_type, "scopeId": g.scope_id, "permission": g.permission, "expiresAt": _iso(g.expires_at), "status": g.status}


@router.delete("/agents/{agent_id}/share-grants/{grant_id}")
def delete_share(agent_id: str, grant_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("agent:share"))]):
    if not scoped_agent(db, auth, agent_id):
        raise BusinessError(400001, "invalid request", 404)
    grant = db.get(ShareGrant, grant_id)
    if grant and grant.agent_id == agent_id:
        before = share_dto(grant)
        reclaimed = reclaim_share_seats(db, grant, auth.user.id, "share revoked")
        grant.status = "revoked"
        audit(db, auth.user.id, "share", "revoke", "share_grant", grant.id, before=before, after=share_dto(grant) | {"reclaimedSeats": reclaimed})
        db.delete(grant)
        db.commit()
        return success({"id": grant_id, "status": "revoked", "reclaimedSeats": reclaimed}, request.state.request_id)
    return success({}, request.state.request_id)


@router.get("/diagnosis-kb")
def diagnosis_kb(db: Db, request: Request, auth: Auth, page: int = 1, pageSize: int = 20, module: str | None = None, errorCode: str | None = None, keyword: str | None = None):
    stmt = select(DiagnosisKb)
    if module:
        stmt = stmt.where(DiagnosisKb.module == module)
    if errorCode:
        stmt = stmt.where(DiagnosisKb.error_code == errorCode)
    rows = db.execute(stmt).scalars().all()
    if keyword:
        keyword_lower = keyword.lower()
        rows = [
            row
            for row in rows
            if keyword_lower
            in " ".join(
                [
                    row.error_code or "",
                    row.module or "",
                    row.symptom or "",
                    row.reason or "",
                    row.solution or "",
                    row.verification_method or "",
                    " ".join(row.tags or []),
                ]
            ).lower()
        ]
    data = [diagnosis_kb_dto(r) for r in rows]
    return success(paginate(data, page, pageSize), request.state.request_id)


def diagnosis_kb_dto(row: DiagnosisKb) -> dict[str, Any]:
    return {
        "id": row.id,
        "errorCode": row.error_code,
        "module": row.module,
        "symptom": row.symptom,
        "reason": row.reason,
        "solution": row.solution,
        "verificationMethod": row.verification_method,
        "tags": row.tags,
    }


@router.post("/diagnosis-kb")
def create_diagnosis_kb(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("ops:manage"))], payload: dict[str, Any] = Body(...)):
    row = DiagnosisKb(
        id=new_id("dkb"),
        error_code=payload.get("errorCode"),
        module=payload["module"],
        symptom=payload["symptom"],
        reason=payload["reason"],
        solution=payload["solution"],
        verification_method=payload.get("verificationMethod"),
        tags=payload.get("tags", []),
    )
    db.add(row)
    audit(db, auth.user.id, "diagnosis", "create_kb", "diagnosis_kb", row.id, after=diagnosis_kb_dto(row))
    db.commit()
    return success(diagnosis_kb_dto(row), request.state.request_id)


@router.put("/diagnosis-kb/{entry_id}")
def update_diagnosis_kb(entry_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("ops:manage"))], payload: dict[str, Any] = Body(...)):
    row = db.get(DiagnosisKb, entry_id)
    if not row:
        raise BusinessError(400001, "invalid request", 404)
    row.error_code = payload.get("errorCode", row.error_code)
    row.module = payload.get("module", row.module)
    row.symptom = payload.get("symptom", row.symptom)
    row.reason = payload.get("reason", row.reason)
    row.solution = payload.get("solution", row.solution)
    row.verification_method = payload.get("verificationMethod", row.verification_method)
    row.tags = payload.get("tags", row.tags)
    audit(db, auth.user.id, "diagnosis", "update_kb", "diagnosis_kb", row.id, after=diagnosis_kb_dto(row))
    db.commit()
    return success(diagnosis_kb_dto(row), request.state.request_id)


@router.delete("/diagnosis-kb/{entry_id}")
def delete_diagnosis_kb(entry_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("ops:manage"))]):
    row = db.get(DiagnosisKb, entry_id)
    if row:
        before = diagnosis_kb_dto(row)
        db.delete(row)
        audit(db, auth.user.id, "diagnosis", "delete_kb", "diagnosis_kb", entry_id, before=before)
        db.commit()
    return success({}, request.state.request_id)


@router.post("/diagnosis-kb/from-diagnosis/{diagnosis_id}")
def diagnosis_kb_from_ticket(diagnosis_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("ops:manage"))]):
    ticket = db.get(DiagnosisTicket, diagnosis_id)
    row = DiagnosisKb(
        id=new_id("dkb"),
        error_code=None,
        module=ticket.object_type if ticket else "manual",
        symptom=ticket.summary if ticket else "历史故障",
        reason=ticket.root_cause if ticket else "待补充",
        solution=ticket.suggestion if ticket else "待补充",
        verification_method="复查关联告警、指标和修复任务状态均已恢复正常",
        tags=["from-diagnosis"],
    )
    db.add(row)
    audit(db, auth.user.id, "diagnosis", "kb_from_diagnosis", "diagnosis_kb", row.id, after=diagnosis_kb_dto(row))
    db.commit()
    return success(diagnosis_kb_dto(row), request.state.request_id)


def diagnosis_decision_tree_dto(row: DiagnosisDecisionTree) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "module": row.module,
        "status": row.status,
        "version": row.version,
        "nodes": row.nodes,
        "edges": row.edges,
        "entryNodeId": row.entry_node_id,
        "createdBy": row.created_by,
        "updatedBy": row.updated_by,
        "createdAt": _iso(row.created_at),
        "updatedAt": _iso(row.updated_at),
    }


@router.get("/diagnosis-decision-trees")
def diagnosis_decision_trees(db: Db, request: Request, auth: Auth, page: int = 1, pageSize: int = 20, module: str | None = None, status: str | None = None):
    stmt = select(DiagnosisDecisionTree)
    if module:
        stmt = stmt.where(DiagnosisDecisionTree.module == module)
    if status:
        stmt = stmt.where(DiagnosisDecisionTree.status == status)
    rows = db.execute(stmt.order_by(DiagnosisDecisionTree.updated_at.desc())).scalars().all()
    return success(paginate([diagnosis_decision_tree_dto(row) for row in rows], page, pageSize), request.state.request_id)


@router.post("/diagnosis-decision-trees")
def create_diagnosis_decision_tree(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("ops:manage"))], payload: dict[str, Any] = Body(...)):
    row = DiagnosisDecisionTree(
        id=new_id("dtree"),
        name=payload.get("name", "诊断决策树"),
        module=payload.get("module", "general"),
        status=payload.get("status", "enabled"),
        version=1,
        nodes=payload.get("nodes", []),
        edges=payload.get("edges", []),
        entry_node_id=payload.get("entryNodeId"),
        created_by=auth.user.id,
        updated_by=auth.user.id,
    )
    db.add(row)
    audit(db, auth.user.id, "diagnosis", "create_decision_tree", "diagnosis_decision_tree", row.id, after=diagnosis_decision_tree_dto(row))
    db.commit()
    return success(diagnosis_decision_tree_dto(row), request.state.request_id)


@router.put("/diagnosis-decision-trees/{tree_id}")
def update_diagnosis_decision_tree(tree_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("ops:manage"))], payload: dict[str, Any] = Body(...)):
    row = db.get(DiagnosisDecisionTree, tree_id)
    if not row:
        raise BusinessError(400001, "invalid request", 404)
    before = diagnosis_decision_tree_dto(row)
    row.name = payload.get("name", row.name)
    row.module = payload.get("module", row.module)
    row.status = payload.get("status", row.status)
    row.nodes = payload.get("nodes", row.nodes)
    row.edges = payload.get("edges", row.edges)
    row.entry_node_id = payload.get("entryNodeId", row.entry_node_id)
    row.version += 1
    row.updated_by = auth.user.id
    audit(db, auth.user.id, "diagnosis", "update_decision_tree", "diagnosis_decision_tree", row.id, before=before, after=diagnosis_decision_tree_dto(row))
    db.commit()
    return success(diagnosis_decision_tree_dto(row), request.state.request_id)


@router.get("/model-quotas")
def model_quotas(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("model:manage"))]):
    return success([{"id": q.id, "scopeType": q.scope_type, "scopeId": q.scope_id, "modelId": q.model_id, "qpsLimit": q.qps_limit, "dailyCallLimit": q.daily_call_limit, "dailyTokenLimit": q.daily_token_limit} for q in db.execute(select(ModelQuotaPolicy)).scalars().all()], request.state.request_id)


@router.post("/model-quotas")
def create_model_quota(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("model:manage"))], payload: dict[str, Any] = Body(...)):
    q = ModelQuotaPolicy(id=new_id("mq"), scope_type=payload["scopeType"], scope_id=payload["scopeId"], model_id=payload.get("modelId"), qps_limit=payload.get("qpsLimit"), daily_call_limit=payload.get("dailyCallLimit"), daily_token_limit=payload.get("dailyTokenLimit"))
    db.add(q)
    after = {"id": q.id, "scopeType": q.scope_type, "scopeId": q.scope_id, "modelId": q.model_id, "qpsLimit": q.qps_limit, "dailyCallLimit": q.daily_call_limit, "dailyTokenLimit": q.daily_token_limit}
    audit(db, auth.user.id, "model", "create_quota", "model_quota", q.id, after=after)
    db.commit()
    return success({"id": q.id}, request.state.request_id)


@router.put("/model-quotas/{quota_id}")
def update_model_quota(quota_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("model:manage"))], payload: dict[str, Any] = Body(...)):
    q = db.get(ModelQuotaPolicy, quota_id)
    if not q:
        raise BusinessError(400001, "invalid request", 404)
    before = {"id": q.id, "scopeType": q.scope_type, "scopeId": q.scope_id, "modelId": q.model_id, "qpsLimit": q.qps_limit, "dailyCallLimit": q.daily_call_limit, "dailyTokenLimit": q.daily_token_limit}
    q.qps_limit = payload.get("qpsLimit", q.qps_limit)
    q.daily_call_limit = payload.get("dailyCallLimit", q.daily_call_limit)
    q.daily_token_limit = payload.get("dailyTokenLimit", q.daily_token_limit)
    after = {"id": q.id, "scopeType": q.scope_type, "scopeId": q.scope_id, "modelId": q.model_id, "qpsLimit": q.qps_limit, "dailyCallLimit": q.daily_call_limit, "dailyTokenLimit": q.daily_token_limit}
    audit(db, auth.user.id, "model", "update_quota", "model_quota", q.id, before=before, after=after)
    db.commit()
    return success({"id": q.id}, request.state.request_id)


@router.delete("/model-quotas/{quota_id}")
def delete_model_quota(quota_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("model:manage"))]):
    q = db.get(ModelQuotaPolicy, quota_id)
    if q:
        before = {"id": q.id, "scopeType": q.scope_type, "scopeId": q.scope_id, "modelId": q.model_id, "qpsLimit": q.qps_limit, "dailyCallLimit": q.daily_call_limit, "dailyTokenLimit": q.daily_token_limit}
        db.delete(q)
        audit(db, auth.user.id, "model", "delete_quota", "model_quota", quota_id, before=before)
        db.commit()
    return success({}, request.state.request_id)


@router.get("/model-route-policies")
def route_policies(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("model:manage"))]):
    return success([{"id": p.id, "scopeType": p.scope_type, "strategy": p.strategy, "primaryModelId": p.primary_model_id, "backupModelId": p.backup_model_id, "fallbackPolicy": p.fallback_policy} for p in db.execute(select(ModelRoutePolicy)).scalars().all()], request.state.request_id)


@router.post("/model-route-policies")
def create_route_policy(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("model:manage"))], payload: dict[str, Any] = Body(...)):
    p = ModelRoutePolicy(id=new_id("mrp"), scope_type=payload["scopeType"], strategy=payload["strategy"], primary_model_id=payload.get("primaryModelId"), backup_model_id=payload.get("backupModelId"), fallback_policy=payload.get("fallbackPolicy", {}))
    db.add(p)
    after = {"id": p.id, "scopeType": p.scope_type, "strategy": p.strategy, "primaryModelId": p.primary_model_id, "backupModelId": p.backup_model_id, "fallbackPolicy": p.fallback_policy}
    audit(db, auth.user.id, "model", "create_route_policy", "model_route_policy", p.id, after=after)
    db.commit()
    return success({"id": p.id}, request.state.request_id)


@router.put("/model-route-policies/{policy_id}")
def update_route_policy(policy_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("model:manage"))], payload: dict[str, Any] = Body(...)):
    p = db.get(ModelRoutePolicy, policy_id)
    if not p:
        raise BusinessError(400001, "invalid request", 404)
    before = {"id": p.id, "scopeType": p.scope_type, "strategy": p.strategy, "primaryModelId": p.primary_model_id, "backupModelId": p.backup_model_id, "fallbackPolicy": p.fallback_policy}
    p.strategy = payload.get("strategy", p.strategy)
    p.primary_model_id = payload.get("primaryModelId", p.primary_model_id)
    p.backup_model_id = payload.get("backupModelId", p.backup_model_id)
    p.fallback_policy = payload.get("fallbackPolicy", p.fallback_policy)
    after = {"id": p.id, "scopeType": p.scope_type, "strategy": p.strategy, "primaryModelId": p.primary_model_id, "backupModelId": p.backup_model_id, "fallbackPolicy": p.fallback_policy}
    audit(db, auth.user.id, "model", "update_route_policy", "model_route_policy", p.id, before=before, after=after)
    db.commit()
    return success({"id": p.id}, request.state.request_id)


@router.delete("/model-route-policies/{policy_id}")
def delete_route_policy(policy_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("model:manage"))]):
    p = db.get(ModelRoutePolicy, policy_id)
    if p:
        before = {"id": p.id, "scopeType": p.scope_type, "strategy": p.strategy, "primaryModelId": p.primary_model_id, "backupModelId": p.backup_model_id, "fallbackPolicy": p.fallback_policy}
        db.delete(p)
        audit(db, auth.user.id, "model", "delete_route_policy", "model_route_policy", policy_id, before=before)
        db.commit()
    return success({}, request.state.request_id)


@router.get("/model-policy-hits")
def policy_hits(db: Db, request: Request, auth: Auth, startTime: str | None = None, endTime: str | None = None, modelId: str | None = None):
    stmt = select(ModelPolicyHit)
    if modelId:
        stmt = stmt.where(ModelPolicyHit.model_id == modelId)
    if start := _parse_dt(startTime):
        stmt = stmt.where(ModelPolicyHit.created_at >= start)
    if end := _parse_dt(endTime):
        stmt = stmt.where(ModelPolicyHit.created_at <= end)
    rows = db.execute(stmt.order_by(ModelPolicyHit.created_at.desc())).scalars().all()
    return success([{"id": h.id, "modelId": h.model_id, "policyId": h.policy_id, "hitType": h.hit_type, "detail": h.detail, "createdAt": _iso(h.created_at)} for h in rows], request.state.request_id)


@router.get("/channels")
def channels(db: Db, request: Request, auth: Auth):
    return success([channel_dto(c, db) for c in db.execute(select(MessageChannel)).scalars().all()], request.state.request_id)


@router.post("/channels")
def create_channel(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("ops:manage"))], payload: dict[str, Any] = Body(...)):
    c = MessageChannel(
        id=new_id("chn"),
        name=payload["name"],
        type=payload["type"],
        status=payload.get("status", "enabled"),
        callback_url=payload.get("callbackUrl"),
        auth_type=payload.get("authType"),
        owner_id=auth.user.id,
        user_rate_limit_per_minute=payload.get("userRateLimitPerMinute"),
        qps_limit=payload.get("qpsLimit"),
        daily_message_limit=payload.get("dailyMessageLimit"),
    )
    db.add(c)
    audit(db, auth.user.id, "channel", "create", "channel", c.id, after=channel_dto(c))
    channel_audit(db, auth.user.id, "create", c.id, detail=channel_dto(c))
    db.commit()
    return success(channel_dto(c), request.state.request_id)


def channel_dto(c: MessageChannel, db: Session | None = None) -> dict[str, Any]:
    bind_count = 0
    if db is not None:
        bind_count = db.scalar(select(func.count()).select_from(ChannelBindAgent).where(ChannelBindAgent.channel_id == c.id, ChannelBindAgent.status == "active")) or 0
    return {"id": c.id, "name": c.name, "type": c.type, "status": c.status, "callbackUrl": c.callback_url, "authType": c.auth_type, "ownerId": c.owner_id, "boundAgentCount": bind_count, "userRateLimitPerMinute": c.user_rate_limit_per_minute, "qpsLimit": c.qps_limit, "dailyMessageLimit": c.daily_message_limit}


def channel_bind_dto(row: ChannelBindAgent) -> dict[str, Any]:
    return {"id": row.id, "channelId": row.channel_id, "agentId": row.agent_id, "status": row.status, "createdBy": row.created_by, "createdAt": _iso(row.created_at)}


def channel_message_log_dto(row: ChannelMessageLog) -> dict[str, Any]:
    return {"id": row.id, "channelId": row.channel_id, "sourceType": row.source_type, "sourceId": row.source_id, "userId": row.user_id, "agentId": row.agent_id, "messageType": row.message_type, "status": row.status, "result": row.result, "createdAt": _iso(row.created_at)}


def channel_limit_violation(db: Session, channel: MessageChannel, user_id: str | None) -> dict[str, Any] | None:
    now = now_utc()
    if channel.user_rate_limit_per_minute is not None and user_id:
        since = now - timedelta(seconds=60)
        user_count = db.scalar(
            select(func.count()).select_from(ChannelMessageLog).where(
                ChannelMessageLog.channel_id == channel.id,
                ChannelMessageLog.user_id == user_id,
                ChannelMessageLog.created_at >= since,
            )
        ) or 0
        if user_count >= channel.user_rate_limit_per_minute:
            return {"reason": "user_rate_limit", "limit": channel.user_rate_limit_per_minute, "current": user_count}
    if channel.qps_limit is not None:
        since = now - timedelta(seconds=1)
        qps_count = db.scalar(
            select(func.count()).select_from(ChannelMessageLog).where(
                ChannelMessageLog.channel_id == channel.id,
                ChannelMessageLog.created_at >= since,
            )
        ) or 0
        if qps_count >= channel.qps_limit:
            return {"reason": "channel_qps_limit", "limit": channel.qps_limit, "current": qps_count}
    if channel.daily_message_limit is not None:
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        daily_count = db.scalar(
            select(func.count()).select_from(ChannelMessageLog).where(
                ChannelMessageLog.channel_id == channel.id,
                ChannelMessageLog.created_at >= day_start,
            )
        ) or 0
        if daily_count >= channel.daily_message_limit:
            return {"reason": "daily_message_limit", "limit": channel.daily_message_limit, "current": daily_count}
    return None


def channel_agent_violation(db: Session, channel_id: str, agent_id: str | None) -> dict[str, Any] | None:
    if not agent_id:
        return None
    if not db.get(Agent, agent_id):
        return {"reason": "agent_not_found", "agentId": agent_id}
    bound = db.execute(
        select(ChannelBindAgent).where(
            ChannelBindAgent.channel_id == channel_id,
            ChannelBindAgent.agent_id == agent_id,
            ChannelBindAgent.status == "active",
        )
    ).scalar_one_or_none()
    if not bound:
        return {"reason": "agent_not_bound", "agentId": agent_id}
    return None


def channel_audit(
    db: Session,
    actor_id: str | None,
    action: str,
    channel_id: str | None,
    object_type: str = "channel",
    object_id: str | None = None,
    result: str = "success",
    detail: dict[str, Any] | None = None,
    module: str = "channel",
) -> None:
    db.add(
        ChannelAuditLog(
            id=new_id("cha"),
            channel_id=channel_id,
            module=module,
            action=action,
            object_type=object_type,
            object_id=object_id or channel_id,
            actor_id=actor_id,
            result=result,
            detail=detail or {},
        )
    )


def channel_audit_dto(row: ChannelAuditLog) -> dict[str, Any]:
    return {
        "id": row.id,
        "channelId": row.channel_id,
        "module": row.module,
        "action": row.action,
        "objectType": row.object_type,
        "objectId": row.object_id,
        "actorId": row.actor_id,
        "result": row.result,
        "detail": row.detail,
        "createdAt": _iso(row.created_at),
    }


@router.put("/channels/{channel_id}")
def update_channel(channel_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("ops:manage"))], payload: dict[str, Any] = Body(...)):
    c = db.get(MessageChannel, channel_id)
    if not c:
        raise BusinessError(400001, "invalid request", 404)
    before = channel_dto(c)
    c.name = payload.get("name", c.name)
    c.status = payload.get("status", c.status)
    c.callback_url = payload.get("callbackUrl", c.callback_url)
    c.auth_type = payload.get("authType", c.auth_type)
    c.user_rate_limit_per_minute = payload.get("userRateLimitPerMinute", c.user_rate_limit_per_minute)
    c.qps_limit = payload.get("qpsLimit", c.qps_limit)
    c.daily_message_limit = payload.get("dailyMessageLimit", c.daily_message_limit)
    audit(db, auth.user.id, "channel", "update", "channel", c.id, before=before, after=channel_dto(c, db))
    channel_audit(db, auth.user.id, "update", c.id, detail={"before": before, "after": channel_dto(c, db)})
    db.commit()
    return success(channel_dto(c, db), request.state.request_id)


@router.post("/channels/{channel_id}/test")
@router.post("/channels/{channel_id}/reconnect")
@router.post("/channels/{channel_id}/disable")
def channel_action(channel_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("ops:manage"))]):
    action = request.url.path.rsplit("/", 1)[-1]
    channel = db.get(MessageChannel, channel_id)
    if not channel:
        raise BusinessError(400001, "invalid request", 404)
    before = channel_dto(channel)
    if action == "disable":
        channel.status = "disabled"
    elif action == "reconnect":
        channel.status = "enabled"
    result = "ok"
    audit(db, auth.user.id, "channel", action, "channel", channel.id, before=before, after=channel_dto(channel))
    channel_audit(db, auth.user.id, action, channel.id, detail={"before": before, "after": channel_dto(channel), "result": result})
    db.commit()
    return success(channel_dto(channel) | {"action": action, "result": result}, request.state.request_id)


@router.get("/channels/{channel_id}/agents")
def channel_agents(channel_id: str, db: Db, request: Request, auth: Auth):
    if not db.get(MessageChannel, channel_id):
        raise BusinessError(400001, "invalid request", 404, {"field": "channelId"})
    rows = db.execute(select(ChannelBindAgent).where(ChannelBindAgent.channel_id == channel_id).order_by(ChannelBindAgent.created_at.desc())).scalars().all()
    return success({"items": [channel_bind_dto(row) for row in rows]}, request.state.request_id)


@router.put("/channels/{channel_id}/agents")
def update_channel_agents(channel_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("ops:manage"))], payload: dict[str, Any] = Body(...)):
    channel = db.get(MessageChannel, channel_id)
    if not channel:
        raise BusinessError(400001, "invalid request", 404)
    requested = payload.get("agentIds", [])
    for row in db.execute(select(ChannelBindAgent).where(ChannelBindAgent.channel_id == channel_id)).scalars().all():
        row.status = "active" if row.agent_id in requested else "disabled"
    existing_ids = set(db.execute(select(ChannelBindAgent.agent_id).where(ChannelBindAgent.channel_id == channel_id)).scalars().all())
    for agent_id in requested:
        if agent_id not in existing_ids:
            if not db.get(Agent, agent_id):
                raise BusinessError(400001, "invalid request", 422, {"agentId": agent_id})
            db.add(ChannelBindAgent(id=new_id("cba"), channel_id=channel_id, agent_id=agent_id, status="active", created_by=auth.user.id))
    audit(db, auth.user.id, "channel", "bind_agents", "channel", channel_id, after={"agentIds": requested})
    channel_audit(db, auth.user.id, "bind_agents", channel_id, detail={"agentIds": requested})
    db.commit()
    rows = db.execute(select(ChannelBindAgent).where(ChannelBindAgent.channel_id == channel_id, ChannelBindAgent.status == "active")).scalars().all()
    return success({"channelId": channel_id, "agentIds": [row.agent_id for row in rows], "items": [channel_bind_dto(row) for row in rows]}, request.state.request_id)


@router.post("/channels/{channel_id}/messages")
def create_channel_message(channel_id: str, db: Db, request: Request, auth: Auth, payload: dict[str, Any] = Body(...)):
    channel = db.get(MessageChannel, channel_id)
    if not channel:
        raise BusinessError(400001, "invalid request", 404)
    agent_id = payload.get("agentId")
    violation = channel_agent_violation(db, channel_id, agent_id) or channel_limit_violation(db, channel, auth.user.id)
    status = "success" if channel.status == "enabled" and not violation else "failed"
    result = violation or {"message": "queued for delivery" if status == "success" else "channel disabled"}
    row = ChannelMessageLog(id=new_id("cml"), channel_id=channel_id, source_type=payload.get("sourceType", "manual"), source_id=payload.get("sourceId"), user_id=auth.user.id, agent_id=agent_id, message_type=payload.get("messageType", "notification"), status=status, result=result)
    db.add(row)
    audit(db, auth.user.id, "channel", "send_message", "channel_message", row.id, after=channel_message_log_dto(row))
    channel_audit(db, auth.user.id, "send_message", channel_id, object_type="channel_message", object_id=row.id, result=status, detail=channel_message_log_dto(row))
    db.commit()
    if violation:
        code = FORBIDDEN if violation["reason"] in {"agent_not_found", "agent_not_bound"} else QUOTA_EXCEEDED
        status_code = 403 if code == FORBIDDEN else 422
        message = "forbidden" if code == FORBIDDEN else "quota exceeded"
        raise BusinessError(code, message, status_code, violation | {"channelId": channel_id, "messageLogId": row.id})
    return success(channel_message_log_dto(row), request.state.request_id)


@router.get("/channel-message-logs")
def channel_message_logs(db: Db, request: Request, auth: Auth, channelId: str | None = None, sourceType: str | None = None, page: int = 1, pageSize: int = 20):
    stmt = select(ChannelMessageLog)
    if channelId:
        stmt = stmt.where(ChannelMessageLog.channel_id == channelId)
    if sourceType:
        stmt = stmt.where(ChannelMessageLog.source_type == sourceType)
    rows = db.execute(stmt.order_by(ChannelMessageLog.created_at.desc())).scalars().all()
    return success(paginate([channel_message_log_dto(row) for row in rows], page, pageSize), request.state.request_id)


@router.get("/business-systems")
def business_systems(db: Db, request: Request, auth: Auth):
    return success([business_system_dto(s, db) for s in db.execute(select(BusinessSystem)).scalars().all()], request.state.request_id)


def business_system_dto(system: BusinessSystem, db: Session | None = None) -> dict[str, Any]:
    grant_count = 0
    if db is not None:
        grant_count = db.scalar(select(func.count()).select_from(BusinessSystemAgentGrant).where(BusinessSystemAgentGrant.business_system_id == system.id, BusinessSystemAgentGrant.status == "active")) or 0
    return {"id": system.id, "name": system.name, "embedType": system.embed_type, "ssoMode": system.sso_mode, "allowedAgentIds": system.allowed_agent_ids, "status": system.status, "grantCount": grant_count}


def business_system_grant_dto(row: BusinessSystemAgentGrant) -> dict[str, Any]:
    return {"id": row.id, "businessSystemId": row.business_system_id, "agentId": row.agent_id, "permission": row.permission, "status": row.status, "createdBy": row.created_by, "createdAt": _iso(row.created_at)}


def business_system_audit_dto(row: BusinessSystemAuditLog) -> dict[str, Any]:
    return {"id": row.id, "businessSystemId": row.business_system_id, "agentId": row.agent_id, "action": row.action, "source": row.source, "userId": row.user_id, "result": row.result, "detail": row.detail, "createdAt": _iso(row.created_at)}


@router.post("/business-systems")
def create_business_system(db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("ops:manage"))], payload: dict[str, Any] = Body(...)):
    s = BusinessSystem(id=new_id("bs"), name=payload["name"], embed_type=payload.get("embedType", "iframe"), sso_mode=payload.get("ssoMode"), allowed_agent_ids=payload.get("allowedAgentIds", []), status="enabled")
    db.add(s)
    audit(db, auth.user.id, "business_system", "create", "business_system", s.id, after={"id": s.id, "allowedAgentIds": s.allowed_agent_ids})
    channel_audit(db, auth.user.id, "create", None, object_type="business_system", object_id=s.id, detail={"id": s.id, "allowedAgentIds": s.allowed_agent_ids}, module="business_system")
    db.commit()
    return success({"id": s.id}, request.state.request_id)


@router.put("/business-systems/{system_id}/agents")
def update_business_agents(system_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("ops:manage"))], payload: dict[str, Any] = Body(...)):
    s = db.get(BusinessSystem, system_id)
    if not s:
        raise BusinessError(400001, "invalid request", 404)
    before = {"id": s.id, "allowedAgentIds": s.allowed_agent_ids}
    s.allowed_agent_ids = payload.get("agentIds", [])
    for row in db.execute(select(BusinessSystemAgentGrant).where(BusinessSystemAgentGrant.business_system_id == system_id)).scalars().all():
        row.status = "active" if row.agent_id in s.allowed_agent_ids else "disabled"
    existing_ids = set(db.execute(select(BusinessSystemAgentGrant.agent_id).where(BusinessSystemAgentGrant.business_system_id == system_id)).scalars().all())
    for agent_id in s.allowed_agent_ids:
        if agent_id not in existing_ids:
            if not db.get(Agent, agent_id):
                raise BusinessError(400001, "invalid request", 422, {"agentId": agent_id})
            db.add(BusinessSystemAgentGrant(id=new_id("bsg"), business_system_id=system_id, agent_id=agent_id, permission=payload.get("permission", "invoke"), status="active", created_by=auth.user.id))
    audit(db, auth.user.id, "business_system", "update_agents", "business_system", s.id, before=before, after={"id": s.id, "allowedAgentIds": s.allowed_agent_ids})
    channel_audit(db, auth.user.id, "update_agents", None, object_type="business_system", object_id=s.id, detail={"before": before, "after": {"id": s.id, "allowedAgentIds": s.allowed_agent_ids}}, module="business_system")
    db.commit()
    return success({"id": s.id, "allowedAgentIds": s.allowed_agent_ids}, request.state.request_id)


@router.get("/business-systems/{system_id}/agents")
def business_system_agents(system_id: str, db: Db, request: Request, auth: Auth):
    rows = db.execute(select(BusinessSystemAgentGrant).where(BusinessSystemAgentGrant.business_system_id == system_id).order_by(BusinessSystemAgentGrant.created_at.desc())).scalars().all()
    return success({"items": [business_system_grant_dto(row) for row in rows]}, request.state.request_id)


@router.post("/business-systems/{system_id}/access")
def business_system_access(system_id: str, db: Db, request: Request, auth: Auth, payload: dict[str, Any] = Body(...)):
    system = db.get(BusinessSystem, system_id)
    if not system or system.status != "enabled":
        raise BusinessError(400001, "invalid request", 404)
    agent_id = payload.get("agentId")
    source = payload.get("source", request.headers.get("referer"))
    allowed = agent_id in (system.allowed_agent_ids or [])
    if agent_id:
        grant = db.execute(select(BusinessSystemAgentGrant).where(BusinessSystemAgentGrant.business_system_id == system_id, BusinessSystemAgentGrant.agent_id == agent_id, BusinessSystemAgentGrant.status == "active")).scalar_one_or_none()
        allowed = allowed or bool(grant)
    result = "success" if allowed else "forbidden"
    row = BusinessSystemAuditLog(id=new_id("bsa"), business_system_id=system_id, agent_id=agent_id, action=payload.get("action", "embed_access"), source=source, user_id=auth.user.id, result=result, detail={"embedType": system.embed_type, "ssoMode": system.sso_mode})
    db.add(row)
    audit(db, auth.user.id, "business_system", "access", "business_system", system_id, result=result, after=business_system_audit_dto(row))
    channel_audit(db, auth.user.id, "access", None, object_type="business_system", object_id=system_id, result=result, detail=business_system_audit_dto(row), module="business_system")
    db.commit()
    if not allowed:
        raise BusinessError(FORBIDDEN, "forbidden", 403, {"auditId": row.id})
    return success(business_system_audit_dto(row) | {"allowed": True}, request.state.request_id)


@router.get("/business-system-audit-logs")
def business_system_audit_logs(db: Db, request: Request, auth: Auth, systemId: str | None = None, agentId: str | None = None, page: int = 1, pageSize: int = 20):
    stmt = select(BusinessSystemAuditLog)
    if systemId:
        stmt = stmt.where(BusinessSystemAuditLog.business_system_id == systemId)
    if agentId:
        stmt = stmt.where(BusinessSystemAuditLog.agent_id == agentId)
    rows = db.execute(stmt.order_by(BusinessSystemAuditLog.created_at.desc())).scalars().all()
    return success(paginate([business_system_audit_dto(row) for row in rows], page, pageSize), request.state.request_id)


@router.get("/channel-audit-logs")
def channel_audit_logs(db: Db, request: Request, auth: Auth, page: int = 1, pageSize: int = 20, module: str | None = None, action: str | None = None):
    stmt = select(ChannelAuditLog)
    if module:
        stmt = stmt.where(ChannelAuditLog.module == module)
    if action:
        stmt = stmt.where(ChannelAuditLog.action == action)
    rows = db.execute(stmt.order_by(ChannelAuditLog.created_at.desc())).scalars().all()
    return success(paginate([channel_audit_dto(row) for row in rows], page, pageSize), request.state.request_id)


@router.get("/memories")
def memories(db: Db, request: Request, auth: Auth, scope: str | None = None, keyword: str | None = None, page: int = 1, pageSize: int = 20):
    stmt = select(Memory)
    if (auth.data_scope or {}).get("type") != "all":
        stmt = stmt.where(or_(Memory.owner_id == auth.user.id, Memory.scope.in_(["organization", "enterprise"])))
    if scope:
        stmt = stmt.where(Memory.scope == scope)
    if keyword:
        stmt = stmt.where(or_(Memory.title.like(f"%{keyword}%"), Memory.content_summary.like(f"%{keyword}%")))
    rows = db.execute(stmt.order_by(Memory.created_at.desc())).scalars().all()
    return success(paginate([{"id": m.id, "scope": m.scope, "ownerId": m.owner_id, "title": m.title, "contentSummary": m.content_summary, "status": m.status} for m in rows], page, pageSize), request.state.request_id)


@router.post("/memories")
def create_memory(db: Db, request: Request, auth: Auth, payload: dict[str, Any] = Body(...)):
    m = Memory(id=new_id("mem"), scope=payload.get("scope", "personal"), owner_id=auth.user.id, title=payload["title"], content_summary=payload.get("contentSummary"), status="active")
    db.add(m)
    audit(db, auth.user.id, "memory", "create", "memory", m.id, after={"scope": m.scope, "ownerId": m.owner_id, "title": m.title, "status": m.status})
    db.commit()
    return success({"id": m.id}, request.state.request_id)


@router.put("/memories/{memory_id}")
def update_memory(memory_id: str, db: Db, request: Request, auth: Auth, payload: dict[str, Any] = Body(...)):
    m = db.get(Memory, memory_id)
    if not m:
        raise BusinessError(400001, "invalid request", 404)
    if m.owner_id != auth.user.id and (auth.data_scope or {}).get("type") != "all":
        deny_business_permission(db, auth, "memory:manage", {"memoryId": memory_id})
    before = {"scope": m.scope, "ownerId": m.owner_id, "title": m.title, "contentSummary": m.content_summary, "status": m.status}
    m.title = payload.get("title", m.title)
    m.content_summary = payload.get("contentSummary", m.content_summary)
    after = {"scope": m.scope, "ownerId": m.owner_id, "title": m.title, "contentSummary": m.content_summary, "status": m.status}
    audit(db, auth.user.id, "memory", "update", "memory", m.id, before=before, after=after)
    db.commit()
    return success({"id": m.id, "title": m.title}, request.state.request_id)


@router.delete("/memories/{memory_id}")
def delete_memory(memory_id: str, db: Db, request: Request, auth: Auth):
    m = db.get(Memory, memory_id)
    if m:
        if m.owner_id != auth.user.id and (auth.data_scope or {}).get("type") != "all":
            deny_business_permission(db, auth, "memory:manage", {"memoryId": memory_id})
        before = {"scope": m.scope, "ownerId": m.owner_id, "title": m.title, "contentSummary": m.content_summary, "status": m.status}
        db.delete(m)
        audit(db, auth.user.id, "memory", "delete", "memory", memory_id, before=before)
        db.commit()
    return success({}, request.state.request_id)


@router.post("/memories/{memory_id}/share")
def share_memory(memory_id: str, db: Db, request: Request, auth: Auth, payload: dict[str, Any] = Body(default_factory=dict)):
    memory = db.get(Memory, memory_id)
    if not memory:
        raise BusinessError(400001, "invalid request", 404)
    if memory.owner_id != auth.user.id and (auth.data_scope or {}).get("type") != "all":
        deny_business_permission(db, auth, "memory:share", {"memoryId": memory_id})
    target_scope = payload.get("scope", "organization")
    target_id = payload.get("targetId")
    request_row = MemoryShareRequest(
        id=new_id("msr"),
        memory_id=memory_id,
        requester_id=auth.user.id,
        target_scope=target_scope,
        target_id=target_id,
        status="pending",
        reason=payload.get("reason"),
    )
    approval = ApprovalRequest(
        id=new_id("apr"),
        type="memory_share",
        risk_level="high" if target_scope in {"organization", "enterprise"} else "normal",
        applicant_id=auth.user.id,
        status="pending",
        reason=payload.get("reason"),
        payload_snapshot={"memoryShareRequestId": request_row.id, "memoryId": memory_id, "targetScope": target_scope, "targetId": target_id},
    )
    request_row.approval_id = approval.id
    db.add(request_row)
    db.add(approval)
    db.flush()
    ensure_approval_step(db, approval)
    audit(db, auth.user.id, "memory", "share_request", "memory", memory_id, after=approval.payload_snapshot)
    db.commit()
    return success({"memoryId": memory_id, "status": "pending_review", "scope": target_scope, "shareRequestId": request_row.id, "approvalId": approval.id}, request.state.request_id)


@router.get("/memory-share-requests")
def memory_share_requests(db: Db, request: Request, auth: Auth, status: str | None = None, memoryId: str | None = None, page: int = 1, pageSize: int = 20):
    stmt = select(MemoryShareRequest)
    if status:
        stmt = stmt.where(MemoryShareRequest.status == status)
    if memoryId:
        stmt = stmt.where(MemoryShareRequest.memory_id == memoryId)
    rows = db.execute(stmt.order_by(MemoryShareRequest.created_at.desc())).scalars().all()
    return success(paginate([memory_share_request_dto(row) for row in rows], page, pageSize), request.state.request_id)


def memory_share_request_dto(row: MemoryShareRequest) -> dict[str, Any]:
    return {"id": row.id, "memoryId": row.memory_id, "requesterId": row.requester_id, "targetScope": row.target_scope, "targetId": row.target_id, "status": row.status, "approvalId": row.approval_id, "reason": row.reason, "createdAt": _iso(row.created_at), "decidedAt": _iso(row.decided_at)}


@router.get("/agents/{agent_id}/runtime-skills")
def runtime_skills(agent_id: str, db: Db, request: Request, auth: Auth):
    if not scoped_agent(db, auth, agent_id):
        raise BusinessError(400001, "invalid request", 404, {"field": "agentId"})
    rows = db.execute(select(AgentBindSkill).where(AgentBindSkill.agent_id == agent_id)).scalars().all()
    items = []
    for row in rows:
        skill = db.get(Skill, row.skill_id)
        expected_version = skill.version if skill else None
        drift = row.status != "installed" or (expected_version is not None and row.installed_version != expected_version)
        items.append(
            {
                "skillId": row.skill_id,
                "packageName": row.package_name,
                "status": row.status,
                "installedVersion": row.installed_version,
                "expectedVersion": expected_version,
                "drift": drift,
                "errorMessage": "skill install failed" if row.status == "failed" else None,
            }
        )
    return success({"items": items, "dataSource": "database"}, request.state.request_id)


@router.get("/agents/{agent_id}/skill-env-vars")
def skill_env_vars(agent_id: str, db: Db, request: Request, auth: Auth):
    if not scoped_agent(db, auth, agent_id):
        raise BusinessError(400001, "invalid request", 404, {"field": "agentId"})
    rows = db.execute(select(SkillEnvVar).where(SkillEnvVar.agent_id == agent_id)).scalars().all()
    return success({"items": [{"skillId": r.skill_id, "envName": r.env_name, "maskedValue": r.masked_value, "updatedAt": _iso(r.updated_at)} for r in rows]}, request.state.request_id)


@router.put("/agents/{agent_id}/skill-env-vars")
def put_skill_env_vars(agent_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("agent:ops"))], payload: dict[str, Any] = Body(...)):
    agent = scoped_agent(db, auth, agent_id)
    if not agent:
        raise BusinessError(400001, "invalid request", 404)
    skill_id = payload["skillId"]
    if not db.get(Skill, skill_id):
        raise BusinessError(400001, "invalid request", 422, {"field": "skillId"})
    updated = []
    for key, value in (payload.get("env") or {}).items():
        row = db.execute(
            select(SkillEnvVar).where(
                SkillEnvVar.agent_id == agent_id,
                SkillEnvVar.skill_id == skill_id,
                SkillEnvVar.env_name == key,
            )
        ).scalar_one_or_none()
        if not row:
            row = SkillEnvVar(id=new_id("env"), agent_id=agent_id, skill_id=skill_id, env_name=key, secret_ref=new_id("sec"), masked_value=mask_secret(str(value)))
            db.add(row)
        else:
            row.secret_ref = new_id("sec")
            row.masked_value = mask_secret(str(value))
            row.updated_at = now_utc()
        updated.append({"envName": key, "maskedValue": row.masked_value})
    task = task_for_agent(db, agent, "restart", "queued") if payload.get("restartAfterUpdated", False) and updated else None
    audit(db, auth.user.id, "skill_env", "upsert", "agent", agent_id, after={"skillId": skill_id, "envNames": [item["envName"] for item in updated], "restartTaskId": task.id if task else None})
    db.commit()
    return success({"agentId": agent_id, "skillId": skill_id, "updated": updated, "restartAfterUpdated": bool(task), "restartTaskId": task.id if task else None}, request.state.request_id)


@router.delete("/agents/{agent_id}/skill-env-vars")
def delete_skill_env_vars(agent_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("agent:ops"))], payload: dict[str, Any] = Body(default_factory=dict)):
    if not scoped_agent(db, auth, agent_id):
        raise BusinessError(400001, "invalid request", 404, {"field": "agentId"})
    stmt = select(SkillEnvVar).where(SkillEnvVar.agent_id == agent_id)
    if payload.get("skillId"):
        stmt = stmt.where(SkillEnvVar.skill_id == payload.get("skillId"))
    if payload.get("envNames"):
        stmt = stmt.where(SkillEnvVar.env_name.in_(payload.get("envNames")))
    rows = db.execute(stmt).scalars().all()
    deleted = [{"skillId": row.skill_id, "envName": row.env_name} for row in rows]
    for row in rows:
        db.delete(row)
    audit(db, auth.user.id, "skill_env", "delete", "agent", agent_id, after={"deleted": deleted})
    db.commit()
    return success({"agentId": agent_id, "deleted": deleted}, request.state.request_id)


def validate_dev_path(path: str) -> None:
    root = "/root/.openclaw"
    if (path != root and not path.startswith(f"{root}/")) or ".." in path:
        raise BusinessError(400001, "invalid request", 422, {"field": "path"})


def latest_dev_file_audit(db: Session, agent_id: str, path: str) -> AgentDevFileAudit | None:
    return db.execute(
        select(AgentDevFileAudit)
        .where(AgentDevFileAudit.agent_id == agent_id, AgentDevFileAudit.path == path, AgentDevFileAudit.result == "success")
        .order_by(AgentDevFileAudit.created_at.desc())
    ).scalars().first()


def dev_file_item(row: AgentDevFileAudit) -> dict[str, Any]:
    return {"path": row.path, "etag": row.etag, "operation": row.operation, "updatedAt": _iso(row.created_at), "operatorId": row.operator_id}


@router.get("/agents/{agent_id}/dev-files")
def dev_files(agent_id: str, db: Db, request: Request, auth: Auth, path: str = "/root/.openclaw", page: int = 1, pageSize: int = 20):
    validate_dev_path(path)
    if not scoped_agent(db, auth, agent_id):
        raise BusinessError(400001, "invalid request", 404, {"field": "agentId"})
    rows = db.execute(
        select(AgentDevFileAudit)
        .where(AgentDevFileAudit.agent_id == agent_id, AgentDevFileAudit.path.like(f"{path}%"), AgentDevFileAudit.result == "success")
        .order_by(AgentDevFileAudit.created_at.desc())
    ).scalars().all()
    latest_by_path: dict[str, AgentDevFileAudit] = {}
    for row in rows:
        latest_by_path.setdefault(row.path, row)
    return success(paginate([dev_file_item(row) for row in latest_by_path.values()], page, pageSize), request.state.request_id)


@router.get("/agents/{agent_id}/dev-files/search")
def dev_file_search(agent_id: str, db: Db, request: Request, auth: Auth, keyword: str, path: str = "/root/.openclaw"):
    validate_dev_path(path)
    if not scoped_agent(db, auth, agent_id):
        raise BusinessError(400001, "invalid request", 404, {"field": "agentId"})
    rows = db.execute(
        select(AgentDevFileAudit)
        .where(AgentDevFileAudit.agent_id == agent_id, AgentDevFileAudit.path.like(f"{path}%"), AgentDevFileAudit.path.like(f"%{keyword}%"), AgentDevFileAudit.result == "success")
        .order_by(AgentDevFileAudit.created_at.desc())
    ).scalars().all()
    latest_by_path: dict[str, AgentDevFileAudit] = {}
    for row in rows:
        latest_by_path.setdefault(row.path, row)
    return success({"items": [dev_file_item(row) for row in latest_by_path.values()], "keyword": keyword}, request.state.request_id)


@router.get("/agents/{agent_id}/dev-file/meta")
def dev_file_meta(agent_id: str, db: Db, request: Request, auth: Auth, path: str):
    validate_dev_path(path)
    if not scoped_agent(db, auth, agent_id):
        raise BusinessError(400001, "invalid request", 404, {"field": "agentId"})
    latest = latest_dev_file_audit(db, agent_id, path)
    return success({"path": path, "etag": latest.etag if latest else hashlib.md5(path.encode()).hexdigest(), "size": 0, "updatedAt": _iso(latest.created_at) if latest else None}, request.state.request_id)


@router.get("/agents/{agent_id}/dev-file/content")
def dev_file_content(agent_id: str, db: Db, request: Request, auth: Auth, path: str):
    validate_dev_path(path)
    if not scoped_agent(db, auth, agent_id):
        raise BusinessError(400001, "invalid request", 404, {"field": "agentId"})
    latest = latest_dev_file_audit(db, agent_id, path)
    etag = latest.etag if latest else hashlib.md5(path.encode()).hexdigest()
    return success({"path": path, "content": "", "etag": etag, "updatedAt": _iso(latest.created_at) if latest else None}, request.state.request_id)


@router.put("/agents/{agent_id}/dev-file/content")
def save_dev_file(agent_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("agent:ops"))], payload: dict[str, Any] = Body(...)):
    validate_dev_path(payload["path"])
    if not scoped_agent(db, auth, agent_id):
        raise BusinessError(400001, "invalid request", 404, {"field": "agentId"})
    latest = latest_dev_file_audit(db, agent_id, payload["path"])
    expected = payload.get("etag")
    if expected and latest and expected != latest.etag:
        raise BusinessError(INVALID_STATE, "etag conflict", 409, {"path": payload["path"], "currentEtag": latest.etag})
    etag = hashlib.md5(payload.get("content", "").encode()).hexdigest()
    row = AgentDevFileAudit(id=new_id("dfa"), agent_id=agent_id, operation="save", path=payload["path"], etag=etag, operator_id=auth.user.id, result="success")
    db.add(row)
    audit(db, auth.user.id, "dev_file", "save", "dev_file", payload["path"], after={"agentId": agent_id, "etag": etag})
    db.commit()
    return success({"path": payload["path"], "etag": etag, "auditId": row.id}, request.state.request_id)


@router.get("/agents/{agent_id}/dev-file/download")
def download_dev_file(agent_id: str, db: Db, request: Request, auth: Auth, path: str):
    validate_dev_path(path)
    if not scoped_agent(db, auth, agent_id):
        raise BusinessError(400001, "invalid request", 404, {"field": "agentId"})
    return success({"downloadUrl": f"/api/v1/astron-claw/agents/{agent_id}/dev-file/downloaded?path={path}"}, request.state.request_id)


@router.get("/agents/{agent_id}/memory-preview")
def memory_preview(agent_id: str, db: Db, request: Request, auth: Auth):
    if not scoped_agent(db, auth, agent_id):
        raise BusinessError(400001, "invalid request", 404, {"field": "agentId"})
    plugin = astronmem_row(db, agent_id)
    memories = db.execute(select(Memory).where(Memory.owner_id == agent_id, Memory.scope != "plugin:astronmem")).scalars().all()
    return success(
        {
            "agentId": agent_id,
            "pluginStatus": plugin.status if plugin else "disabled",
            "items": [{"id": m.id, "title": m.title, "contentSummary": m.content_summary, "status": m.status} for m in memories],
        },
        request.state.request_id,
    )


def astronmem_row(db: Session, agent_id: str) -> Memory | None:
    return db.execute(select(Memory).where(Memory.owner_id == agent_id, Memory.scope == "plugin:astronmem")).scalar_one_or_none()


def astronmem_dto(agent_id: str, row: Memory | None) -> dict[str, Any]:
    return {
        "agentId": agent_id,
        "pluginName": "astronmem-cloud-openclaw-plugin",
        "status": row.status if row else "disabled",
        "updatedAt": _iso(row.created_at) if row else None,
    }


@router.get("/agents/{agent_id}/plugins/astronmem")
def astronmem_status(agent_id: str, db: Db, request: Request, auth: Auth):
    if not scoped_agent(db, auth, agent_id):
        raise BusinessError(400001, "invalid request", 404, {"field": "agentId"})
    return success(astronmem_dto(agent_id, astronmem_row(db, agent_id)), request.state.request_id)


@router.post("/agents/{agent_id}/plugins/astronmem")
def astronmem_toggle(agent_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("agent:ops"))], payload: dict[str, Any] = Body(...)):
    if not scoped_agent(db, auth, agent_id):
        raise BusinessError(400001, "invalid request", 404, {"field": "agentId"})
    action = payload.get("action")
    if action not in {"enable", "disable"}:
        raise BusinessError(400001, "invalid request", 422, {"field": "action"})
    status = "enabled" if action == "enable" else "disabled"
    row = astronmem_row(db, agent_id)
    before = astronmem_dto(agent_id, row)
    if not row:
        row = Memory(id=new_id("mem"), scope="plugin:astronmem", owner_id=agent_id, title="AstronMem Plugin", content_summary="runtime plugin state", status=status)
        db.add(row)
    else:
        row.status = status
    after = astronmem_dto(agent_id, row)
    audit(db, auth.user.id, "memory", "astronmem_toggle", "agent", agent_id, before=before, after=after)
    db.commit()
    return success(after, request.state.request_id)


@router.post("/agents/{agent_id}/crons")
def create_cron(agent_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("agent:ops"))], payload: dict[str, Any] = Body(...)):
    if not db.get(Agent, agent_id):
        raise BusinessError(400001, "invalid request", 404, {"field": "agentId"})
    cron = AgentCron(id=new_id("cron"), agent_id=agent_id, name=payload["name"], expression=payload["expression"], type=payload.get("type", "cron"), task=payload["task"], time_zone=payload.get("timeZone", "Asia/Shanghai"), channel=payload.get("channel"), status="enabled", proxy_cron_id=new_id("proxy_cron"))
    db.add(cron)
    audit(db, auth.user.id, "cron", "create", "agent_cron", cron.id, after=cron_dto(cron))
    db.commit()
    return success(cron_dto(cron), request.state.request_id)


@router.get("/agents/{agent_id}/crons")
def list_crons(agent_id: str, db: Db, request: Request, auth: Auth):
    if not db.get(Agent, agent_id):
        raise BusinessError(400001, "invalid request", 404, {"field": "agentId"})
    rows = db.execute(select(AgentCron).where(AgentCron.agent_id == agent_id)).scalars().all()
    return success([cron_dto(c) for c in rows], request.state.request_id)


def cron_dto(c: AgentCron) -> dict[str, Any]:
    return {"id": c.id, "agentId": c.agent_id, "name": c.name, "expression": c.expression, "type": c.type, "task": c.task, "timeZone": c.time_zone, "channel": c.channel, "status": c.status, "proxyCronId": c.proxy_cron_id, "createdAt": _iso(c.created_at)}


@router.put("/agents/{agent_id}/crons/{cron_id}")
def update_cron(agent_id: str, cron_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("agent:ops"))], payload: dict[str, Any] = Body(...)):
    cron = db.get(AgentCron, cron_id)
    if not cron or cron.agent_id != agent_id:
        raise BusinessError(400001, "invalid request", 404, {"field": "cronId"})
    before = cron_dto(cron)
    cron.name = payload.get("name", cron.name)
    cron.expression = payload.get("expression", cron.expression)
    cron.type = payload.get("type", cron.type)
    cron.task = payload.get("task", cron.task)
    cron.time_zone = payload.get("timeZone", cron.time_zone)
    cron.channel = payload.get("channel", cron.channel)
    cron.status = payload.get("status", cron.status)
    audit(db, auth.user.id, "cron", "update", "agent_cron", cron.id, before=before, after=cron_dto(cron))
    db.commit()
    return success(cron_dto(cron), request.state.request_id)


@router.delete("/agents/{agent_id}/crons/{cron_id}")
def delete_cron(agent_id: str, cron_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("agent:ops"))]):
    cron = db.get(AgentCron, cron_id)
    if not cron or cron.agent_id != agent_id:
        raise BusinessError(400001, "invalid request", 404, {"field": "cronId"})
    before = cron_dto(cron)
    db.delete(cron)
    audit(db, auth.user.id, "cron", "delete", "agent_cron", cron_id, before=before)
    db.commit()
    return success({}, request.state.request_id)


@router.get("/agents/{agent_id}/crons/{cron_id}/runs")
def cron_runs(agent_id: str, cron_id: str, db: Db, request: Request, auth: Auth, limit: int = 100):
    cron = db.get(AgentCron, cron_id)
    if not cron or cron.agent_id != agent_id:
        raise BusinessError(400001, "invalid request", 404, {"field": "cronId"})
    rows = db.execute(select(AgentCronRun).where(AgentCronRun.cron_id == cron_id).order_by(AgentCronRun.run_at.desc()).limit(limit)).scalars().all()
    return success({"items": [{"id": row.id, "cronId": row.cron_id, "status": row.status, "summary": row.summary, "error": row.error, "durationMs": row.duration_ms, "runAt": _iso(row.run_at)} for row in rows], "limit": limit}, request.state.request_id)


@router.get("/agents/{agent_id}/teams")
def teams(agent_id: str, db: Db, request: Request, auth: Auth, sessionId: str):
    if not db.get(Agent, agent_id):
        raise BusinessError(400001, "invalid request", 404, {"field": "agentId"})
    return success({"items": [], "sessionKey": f"agent:main:main:{sessionId}", "proxyCode": 0, "empty": True}, request.state.request_id)


@router.get("/agents/{agent_id}/teams/{team_id}/progress")
@router.get("/agents/{agent_id}/teams/{team_id}/outputs")
@router.get("/agents/{agent_id}/teams/{team_id}/result")
def team_kind(agent_id: str, team_id: str, db: Db, request: Request, auth: Auth, sessionId: str):
    if not db.get(Agent, agent_id):
        raise BusinessError(400001, "invalid request", 404, {"field": "agentId"})
    kind = request.url.path.rsplit("/", 1)[-1]
    return success({"teamId": team_id, "kind": kind, "sessionKey": f"agent:main:main:{sessionId}", "items": [], "proxyCode": 0, "empty": True}, request.state.request_id)


@router.post("/agents/{agent_id}/backups")
def start_backup(agent_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("agent:ops"))]):
    if not db.get(Agent, agent_id):
        raise BusinessError(400001, "invalid request", 404, {"field": "agentId"})
    task = BackupTask(id=new_id("bkt"), agent_id=agent_id, type="backup", proxy_task_id=new_id("proxy_backup"), status="running", phase="started")
    db.add(task)
    audit(db, auth.user.id, "backup", "start", "agent", agent_id)
    db.commit()
    return success(backup_task_dto(task), request.state.request_id)


@router.get("/agents/{agent_id}/backups/{task_id}")
@router.get("/agents/{agent_id}/backup-restore/{task_id}")
def backup_status(agent_id: str, task_id: str, db: Db, request: Request, auth: Auth):
    task = db.get(BackupTask, task_id)
    if not task or task.agent_id != agent_id:
        raise BusinessError(400001, "invalid request", 404, {"field": "taskId"})
    process_backup_if_mock(task)
    db.commit()
    return success(backup_task_dto(task), request.state.request_id)


@router.post("/agents/{agent_id}/backup-restore")
def restore_backup(agent_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("agent:ops"))], payload: dict[str, Any] = Body(default_factory=dict)):
    if not db.get(Agent, agent_id):
        raise BusinessError(400001, "invalid request", 404, {"field": "agentId"})
    backup_task_id = payload.get("backupTaskId")
    if not backup_task_id:
        raise BusinessError(400001, "invalid request", 422, {"field": "backupTaskId"})
    backup_task = db.get(BackupTask, backup_task_id)
    if not backup_task or backup_task.agent_id != agent_id or backup_task.type != "backup":
        raise BusinessError(400001, "invalid request", 404, {"field": "backupTaskId"})
    process_backup_if_mock(backup_task)
    if backup_task.status != "success":
        raise BusinessError(INVALID_STATE, "invalid state", 409, {"backupTaskId": backup_task.id, "status": backup_task.status})
    task = BackupTask(id=new_id("rst"), agent_id=agent_id, type="restore", proxy_task_id=new_id("proxy_restore"), status="running", phase="started")
    db.add(task)
    audit(db, auth.user.id, "backup", "restore", "agent", agent_id, after={"backupTaskId": backup_task.id, "proxyTaskId": task.proxy_task_id})
    db.commit()
    return success(backup_task_dto(task), request.state.request_id)


@router.delete("/agents/{agent_id}/backups")
def delete_backups(agent_id: str, db: Db, request: Request, auth: Annotated[Principal, Depends(require_permission("agent:ops"))]):
    if not db.get(Agent, agent_id):
        raise BusinessError(400001, "invalid request", 404, {"field": "agentId"})
    tasks = db.execute(select(BackupTask).where(BackupTask.agent_id == agent_id)).scalars().all()
    for task in tasks:
        db.delete(task)
    audit(db, auth.user.id, "backup", "delete", "agent", agent_id)
    db.commit()
    return success({}, request.state.request_id)
