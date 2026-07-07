from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, mask_secret
from app.id_gen import new_id
from app.services.audit_integrity import audit_hash_payload
from app.models import (
    AuditLog,
    Department,
    DiagnosisKb,
    KnowledgeBase,
    LlmModel,
    Permission,
    Role,
    RolePermission,
    SeatAssignment,
    SeatPackage,
    SecurityPolicy,
    Skill,
    User,
    UserRole,
)


PERMISSIONS = [
    ("agent:view", "agent", "agents", "view", "normal"),
    ("agent:create", "agent", "agents", "create", "normal"),
    ("agent:update", "agent", "agents", "update", "normal"),
    ("agent:delete", "agent", "agents", "delete", "high"),
    ("agent:deploy", "agent", "agents", "deploy", "normal"),
    ("agent:batch", "agent", "batch", "execute", "high"),
    ("agent:ops", "agent", "ops", "execute", "high"),
    ("agent:share", "agent", "share", "manage", "normal"),
    ("skill:manage", "skill", "skills", "manage", "normal"),
    ("knowledge:manage", "knowledge", "knowledge", "manage", "normal"),
    ("model:manage", "model", "models", "manage", "high"),
    ("model:secret_view", "model", "models", "secret_view", "critical"),
    ("monitor:view", "monitor", "monitor", "view", "normal"),
    ("alert:manage", "alert", "alerts", "manage", "normal"),
    ("audit:view", "audit", "audit", "view", "high"),
    ("audit:export", "audit", "audit", "export", "high"),
    ("approval:manage", "approval", "approval", "manage", "high"),
    ("seat:manage", "seat", "seat", "manage", "normal"),
    ("ops:manage", "ops", "ops", "manage", "high"),
    ("security:manage", "security", "security", "manage", "high"),
]


def seed_database(db: Session) -> None:
    now = datetime.now(timezone.utc)

    if not db.get(Department, "dep001"):
        db.add_all(
            [
                Department(id="dep001", name="总部", parent_id=None, status="active", source="local"),
                Department(id="dep002", name="运营部", parent_id="dep001", status="active", source="local"),
                Department(id="dep003", name="科技部", parent_id="dep001", status="active", source="local"),
            ]
        )

    for code, module, page, action, risk_level in PERMISSIONS:
        if not db.get(Permission, code):
            db.add(Permission(code=code, module=module, page=page, action=action, risk_level=risk_level))

    if not db.get(Role, "super_admin"):
        db.add(
            Role(
                id="super_admin",
                name="超级管理员",
                description="系统内置超级管理员角色",
                data_scope={"type": "all", "departmentIds": []},
                status="active",
            )
        )
    db.flush()

    existing_role_permissions = {
        row[0]
        for row in db.execute(
            select(RolePermission.permission_code).where(RolePermission.role_id == "super_admin")
        ).all()
    }
    for code, *_ in PERMISSIONS:
        if code not in existing_role_permissions:
            db.add(RolePermission(role_id="super_admin", permission_code=code))

    if not db.get(User, "u001"):
        db.add(
            User(
                id="u001",
                username="admin",
                password_hash=hash_password("Admin@123456"),
                password_updated_at=now,
                name="系统管理员",
                department_id="dep001",
                status="active",
                seat_status="assigned",
                identity_source="local",
                created_at=now,
                updated_at=now,
            )
        )
    db.flush()

    has_admin_role = db.execute(
        select(UserRole.id).where(UserRole.user_id == "u001", UserRole.role_id == "super_admin")
    ).first()
    if not has_admin_role:
        db.add(UserRole(user_id="u001", role_id="super_admin"))

    if not db.get(SeatPackage, "seat_pkg_001"):
        db.add(
            SeatPackage(
                id="seat_pkg_001",
                name="默认席位包",
                total_count=100,
                used_count=1,
                status="active",
            )
        )
        db.flush()
    if not db.get(SeatAssignment, "seat_asg_001"):
        db.add(
            SeatAssignment(
                id="seat_asg_001",
                seat_package_id="seat_pkg_001",
                assignee_type="user",
                assignee_id="u001",
                agent_id=None,
                status="active",
            )
        )

    _seed_model(db, "m001", "xminimaxm26", "api_key:api_secret", 0.01, 850, 23000, 2300000, 120.0)
    _seed_model(db, "m002", "backup-model", "backup_key:backup_secret", 0.008, 920, 1200, 110000, 40.0)

    if not db.get(Skill, "sk001"):
        db.add(
            Skill(
                id="sk001",
                name="图片生成",
                package_name="image_create",
                package_url="https://example.com/skill.zip",
                source="custom",
                version="1.0.0",
                status="enabled",
                category="media",
                creator_id="u001",
                allowed_roles=["super_admin"],
                security_review_status="approved",
            )
        )

    if not db.get(KnowledgeBase, "kb001"):
        db.add(
            KnowledgeBase(
                id="kb001",
                name="寿险知识库",
                scope="department",
                department_id="dep002",
                status="enabled",
                file_count=0,
            )
        )

    diagnosis_seed = db.get(DiagnosisKb, "dkb_001")
    if not diagnosis_seed:
        db.add(
            DiagnosisKb(
                id="dkb_001",
                error_code="400003",
                module="claw_proxy",
                symptom="沙箱会话失效",
                reason="实例会话过期或被清理",
                solution="重新部署智能体并检查同步任务",
                verification_method="重新部署后检查实例同步状态为 running，且 Claw Proxy 会话探针返回成功",
                tags=["sandbox", "session"],
            )
        )
    elif not diagnosis_seed.verification_method:
        diagnosis_seed.verification_method = "重新部署后检查实例同步状态为 running，且 Claw Proxy 会话探针返回成功"

    if not db.get(SecurityPolicy, "sec_pol_001"):
        db.add(
            SecurityPolicy(
                id="sec_pol_001",
                name="模型调用敏感信息脱敏",
                category="model_call",
                status="enabled",
                risk_level="high",
                config={"maskSecrets": True, "denyRawSecretExport": True},
                description="写入模型调用日志前必须脱敏摘要和密钥字段",
            )
        )
    if not db.get(SecurityPolicy, "sec_pol_002"):
        db.add(
            SecurityPolicy(
                id="sec_pol_002",
                name="高危导出审批",
                category="export",
                status="enabled",
                risk_level="high",
                config={"approvalRequired": True, "watermarkRequired": True},
                description="审计与模型调用日志导出必须审批并带水印",
            )
        )

    if not db.get(AuditLog, "aud_seed_001"):
        current = audit_hash_payload(
            hash_prev="",
            actor_id=None,
            module="system",
            action="seed",
            object_type="database",
            object_id="astronclaw",
            result="success",
            error_message=None,
            before_value=None,
            after_value=None,
            created_at=now,
        )
        db.add(
            AuditLog(
                id="aud_seed_001",
                actor_id=None,
                module="system",
                action="seed",
                object_type="database",
                object_id="astronclaw",
                result="success",
                hash_prev="",
                hash_current=current,
                created_at=now,
            )
        )

    db.commit()


def _seed_model(
    db: Session,
    model_id: str,
    name: str,
    api_key: str,
    unit_price: float,
    avg_latency_ms: int,
    today_call_count: int,
    today_tokens: int,
    container_cost: float,
) -> None:
    if db.get(LlmModel, model_id):
        return
    db.add(
        LlmModel(
            id=model_id,
            name=name,
            provider="maas",
            model_key=name,
            type="chat",
            base_url="https://maas-api.example.com/v2",
            auth_type="api_key",
            secret_ref=f"sec_{model_id}",
            api_key_masked=mask_secret(api_key),
            status="enabled",
            unit_price=unit_price,
            context_length=32768,
            applicable_scenarios=["customer_service", "operations"],
            default_timeout_ms=300000,
            error_rate=0,
            avg_latency_ms=avg_latency_ms,
            today_call_count=today_call_count,
            today_tokens=today_tokens,
            container_cost=container_cost,
        )
    )
