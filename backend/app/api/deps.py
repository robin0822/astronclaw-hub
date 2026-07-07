from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BusinessError, FORBIDDEN, UNAUTHORIZED
from app.db import get_db
from app.id_gen import new_id
from app.models import AuditLog, Permission, Role, RolePermission, SessionModel, User, UserRole, now_utc
from app.services.audit_integrity import audit_hash_payload


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def as_aware(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


@dataclass
class Principal:
    user: User
    roles: list[str]
    permissions: list[str]
    data_scope: dict


DbSession = Annotated[Session, Depends(get_db)]


def get_current_principal(
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
) -> Principal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise BusinessError(UNAUTHORIZED, "unauthorized", 401)
    token = authorization.split(" ", 1)[1].strip()
    session = db.execute(
        select(SessionModel).where(
            SessionModel.access_token_hash == token_hash(token),
            SessionModel.revoked_at.is_(None),
        )
    ).scalar_one_or_none()
    if not session or as_aware(session.expires_at) < datetime.now(timezone.utc):
        raise BusinessError(UNAUTHORIZED, "unauthorized", 401)
    user = db.get(User, session.user_id)
    if not user or user.status != "active":
        raise BusinessError(UNAUTHORIZED, "unauthorized", 401)
    return build_principal(db, user)


def build_principal(db: Session, user: User) -> Principal:
    role_ids = [row[0] for row in db.execute(select(UserRole.role_id).where(UserRole.user_id == user.id)).all()]
    permissions = [
        row[0]
        for row in db.execute(
            select(RolePermission.permission_code).where(RolePermission.role_id.in_(role_ids or [""]))
        ).all()
    ]
    role = db.get(Role, role_ids[0]) if role_ids else None
    return Principal(
        user=user,
        roles=role_ids,
        permissions=sorted(set(permissions)),
        data_scope=role.data_scope if role else {"type": "self", "departmentIds": [user.department_id]},
    )


def require_permission(code: str):
    def dependency(db: DbSession, principal: Annotated[Principal, Depends(get_current_principal)]) -> Principal:
        if code not in principal.permissions:
            record_permission_denied(db, principal.user.id, code)
            raise BusinessError(FORBIDDEN, "forbidden", 403)
        return principal

    return dependency


def record_permission_denied(db: Session, actor_id: str | None, permission_code: str) -> None:
    previous = db.execute(select(AuditLog.hash_current).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(1)).scalar_one_or_none() or ""
    created_at = now_utc()
    hash_current = audit_hash_payload(
        hash_prev=previous,
        actor_id=actor_id,
        module="security",
        action="permission_denied",
        object_type="permission",
        object_id=permission_code,
        result="failed",
        error_message="forbidden",
        before_value=None,
        after_value={"permission": permission_code},
        created_at=created_at,
    )
    db.add(
        AuditLog(
            id=new_id("aud"),
            actor_id=actor_id,
            module="security",
            action="permission_denied",
            object_type="permission",
            object_id=permission_code,
            result="failed",
            error_message="forbidden",
            after_value={"permission": permission_code},
            hash_prev=previous,
            hash_current=hash_current,
            created_at=created_at,
        )
    )
    db.commit()
