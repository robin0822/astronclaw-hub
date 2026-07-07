import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("db") / "astronclaw_test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"

    from app.db import Base, SessionLocal, engine
    import app.models  # noqa: F401
    from app.seed import seed_database
    from app.main import app

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_database(db)

    with TestClient(app) as test_client:
        yield test_client
    engine.dispose()


@pytest.fixture()
def auth_headers(client):
    response = client.post(
        "/api/v1/astron-claw/auth/login",
        json={"username": "admin", "password": "Admin@123456"},
    )
    assert response.status_code == 200
    token = response.json()["data"]["accessToken"]
    return {"Authorization": f"Bearer {token}"}


def test_login_me_and_permissions(client, auth_headers):
    me = client.get("/api/v1/astron-claw/me", headers=auth_headers)
    assert me.status_code == 200
    assert me.json()["data"]["username"] == "admin"

    permissions = client.get("/api/v1/astron-claw/me/permissions", headers=auth_headers)
    assert permissions.status_code == 200
    assert "agent:create" in permissions.json()["data"]["permissions"]


def test_org_users_roles_permissions_and_audit(client, auth_headers):
    users = client.get(
        "/api/v1/astron-claw/org/users",
        headers=auth_headers,
        params={"keyword": "admin", "departmentId": "dep001", "status": "active", "seatStatus": "assigned"},
    )
    assert users.status_code == 200
    user_items = users.json()["data"]["items"]
    assert any(item["username"] == "admin" and item["roles"][0]["id"] == "super_admin" for item in user_items)

    matrix = client.get("/api/v1/astron-claw/permission-matrix", headers=auth_headers)
    assert matrix.status_code == 200
    assert any(module["module"] == "agent" for module in matrix.json()["data"])

    role = client.post(
        "/api/v1/astron-claw/roles",
        headers=auth_headers,
        json={
            "id": "ops_viewer",
            "name": "运维查看员",
            "description": "查看和巡检",
            "dataScope": {"type": "department", "departmentIds": ["dep002"]},
            "permissions": ["agent:view", "monitor:view", "missing:permission"],
        },
    )
    assert role.status_code == 200
    role_data = role.json()["data"]
    assert role_data["id"] == "ops_viewer"
    assert role_data["userCount"] == 0
    assert sorted(role_data["permissions"]) == ["agent:view", "monitor:view"]

    listed = client.get("/api/v1/astron-claw/roles", headers=auth_headers, params={"keyword": "运维", "status": "active"})
    assert listed.status_code == 200
    assert listed.json()["data"]["items"][0]["id"] == "ops_viewer"

    updated_permissions = client.put(
        "/api/v1/astron-claw/roles/ops_viewer/permissions",
        headers=auth_headers,
        json={"permissions": ["agent:view", "audit:view"]},
    )
    assert updated_permissions.status_code == 200
    assert sorted(updated_permissions.json()["data"]["permissions"]) == ["agent:view", "audit:view"]

    updated_role = client.put(
        "/api/v1/astron-claw/roles/ops_viewer",
        headers=auth_headers,
        json={"name": "审计查看员", "status": "active", "dataScope": {"type": "self", "departmentIds": []}},
    )
    assert updated_role.status_code == 200
    assert updated_role.json()["data"]["name"] == "审计查看员"
    assert sorted(updated_role.json()["data"]["permissions"]) == ["agent:view", "audit:view"]

    deleted = client.delete("/api/v1/astron-claw/roles/ops_viewer", headers=auth_headers)
    assert deleted.status_code == 200
    disabled = client.get("/api/v1/astron-claw/roles", headers=auth_headers, params={"keyword": "审计查看员", "status": "disabled"})
    assert disabled.json()["data"]["items"][0]["id"] == "ops_viewer"

    audit_logs = client.get(
        "/api/v1/astron-claw/audit/operation-logs",
        headers=auth_headers,
        params={"module": "rbac", "action": "update_role_permissions"},
    )
    assert audit_logs.status_code == 200
    assert any(item["objectId"] == "ops_viewer" for item in audit_logs.json()["data"]["items"])


def test_org_sync_job_imports_departments_and_users(client, auth_headers):
    created = client.post(
        "/api/v1/astron-claw/org/sync-jobs",
        headers=auth_headers,
        json={
            "source": "oa",
            "syncType": "incremental",
            "departments": [{"id": "dep_oa_001", "parentId": "dep001", "name": "OA业务部", "status": "active"}],
            "positions": [{"id": "pos_oa_001", "name": "客户经理", "departmentId": "dep_oa_001", "level": "P6"}],
            "users": [
                {
                    "id": "u_oa_001",
                    "employeeNo": "E1001",
                    "username": "oa_user",
                    "name": "OA User",
                    "departmentId": "dep_oa_001",
                    "email": "oa@example.com",
                    "mobile": "13800000000",
                    "status": "active",
                    "seatStatus": "unassigned",
                    "ssoSubject": "oa:E1001",
                }
            ],
            "userPositions": [{"userId": "u_oa_001", "positionId": "pos_oa_001"}],
        },
    )
    assert created.status_code == 200
    data = created.json()["data"]
    assert data["status"] == "queued"
    assert data["source"] == "oa"
    assert data["syncType"] == "incremental"

    detail = client.get(f"/api/v1/astron-claw/org/sync-jobs/{data['id']}", headers=auth_headers)
    assert detail.status_code == 200
    detail_data = detail.json()["data"]
    assert detail_data["status"] == "success"
    assert detail_data["departmentsSynced"] == 1
    assert detail_data["usersSynced"] == 1

    departments = client.get("/api/v1/astron-claw/org/departments/tree", headers=auth_headers)
    assert any(item["id"] == "dep_oa_001" and item["source"] == "oa" for item in departments.json()["data"])

    users = client.get("/api/v1/astron-claw/org/users", headers=auth_headers, params={"keyword": "oa_user", "departmentId": "dep_oa_001"})
    assert users.status_code == 200
    user = users.json()["data"]["items"][0]
    assert user["employeeNo"] == "E1001"
    assert user["identitySource"] == "oa"
    assert user["seatStatus"] == "unassigned"
    assert user["positions"][0]["id"] == "pos_oa_001"

    positions = client.get("/api/v1/astron-claw/org/positions", headers=auth_headers, params={"departmentId": "dep_oa_001"})
    assert positions.status_code == 200
    assert positions.json()["data"]["items"][0]["name"] == "客户经理"

    jobs = client.get("/api/v1/astron-claw/org/sync-jobs", headers=auth_headers, params={"status": "success", "source": "oa"})
    assert any(item["id"] == data["id"] for item in jobs.json()["data"]["items"])

    audit_logs = client.get(
        "/api/v1/astron-claw/audit/operation-logs",
        headers=auth_headers,
        params={"module": "org", "action": "sync_success"},
    )
    assert any(item["objectId"] == data["id"] for item in audit_logs.json()["data"]["items"])


def test_org_sync_departed_user_revokes_sessions_and_reclaims_seat(client, auth_headers):
    from app.core.security import hash_password
    from app.db import SessionLocal
    from app.models import User

    with SessionLocal() as db:
        db.add(
            User(
                id="u_oa_departed",
                employee_no="E2001",
                username="oa_departed",
                password_hash=hash_password("Departed@123"),
                name="OA Departed",
                department_id="dep001",
                status="active",
                seat_status="unassigned",
                identity_source="oa",
                sso_subject="oa:E2001",
            )
        )
        db.commit()

    seat_pkg = client.post(
        "/api/v1/astron-claw/seat-packages",
        headers=auth_headers,
        json={"name": "oa-departed-seat", "totalCount": 1},
    )
    package_id = seat_pkg.json()["data"]["id"]
    seat = client.post(
        "/api/v1/astron-claw/seat-assignments",
        headers=auth_headers,
        json={"seatPackageId": package_id, "assigneeType": "user", "assigneeId": "u_oa_departed", "reason": "initial allocation"},
    )
    assert seat.status_code == 200
    assignment_id = seat.json()["data"]["id"]

    login = client.post("/api/v1/astron-claw/auth/login", json={"username": "oa_departed", "password": "Departed@123"})
    assert login.status_code == 200
    old_headers = {"Authorization": f"Bearer {login.json()['data']['accessToken']}"}
    assert client.get("/api/v1/astron-claw/me", headers=old_headers).status_code == 200

    sync = client.post(
        "/api/v1/astron-claw/org/sync-jobs",
        headers=auth_headers,
        json={
            "source": "oa",
            "syncType": "incremental",
            "users": [
                {
                    "id": "u_oa_departed",
                    "employeeNo": "E2001",
                    "username": "oa_departed",
                    "name": "OA Departed",
                    "departmentId": "dep001",
                    "status": "departed",
                    "ssoSubject": "oa:E2001",
                }
            ],
        },
    )
    assert sync.status_code == 200
    detail = client.get(f"/api/v1/astron-claw/org/sync-jobs/{sync.json()['data']['id']}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["status"] == "success"

    assert client.get("/api/v1/astron-claw/me", headers=old_headers).status_code == 401

    users = client.get("/api/v1/astron-claw/org/users", headers=auth_headers, params={"keyword": "oa_departed"})
    user = users.json()["data"]["items"][0]
    assert user["status"] == "departed"
    assert user["seatStatus"] == "unassigned"

    assignments = client.get("/api/v1/astron-claw/seat-assignments", headers=auth_headers, params={"userId": "u_oa_departed"})
    assignment = next(item for item in assignments.json()["data"] if item["id"] == assignment_id)
    assert assignment["status"] == "reclaimed"

    packages = client.get("/api/v1/astron-claw/seat-packages", headers=auth_headers)
    package = next(item for item in packages.json()["data"] if item["id"] == package_id)
    assert package["usedCount"] == 0

    events = client.get(
        "/api/v1/astron-claw/seat-events",
        headers=auth_headers,
        params={"assignmentId": assignment_id, "eventType": "reclaim"},
    )
    assert events.status_code == 200
    assert events.json()["data"]["items"][0]["reason"].endswith(":departed")


def test_login_failure_lockout_and_disabled_user(client):
    from app.core.security import hash_password
    from app.db import SessionLocal
    from app.models import User

    with SessionLocal() as db:
        db.add(
            User(
                id="u_lockout",
                username="lockout_user",
                password_hash=hash_password("Lockout@123456"),
                name="Lockout User",
                department_id="dep001",
                status="active",
            )
        )
        db.commit()

    for _ in range(4):
        failed = client.post("/api/v1/astron-claw/auth/login", json={"username": "lockout_user", "password": "wrong"})
        assert failed.status_code == 401
        assert failed.json()["code"] == 401001

    locked = client.post("/api/v1/astron-claw/auth/login", json={"username": "lockout_user", "password": "wrong"})
    assert locked.status_code == 401
    assert locked.json()["code"] == 401002

    still_locked = client.post("/api/v1/astron-claw/auth/login", json={"username": "lockout_user", "password": "Lockout@123456"})
    assert still_locked.status_code == 401
    assert still_locked.json()["code"] == 401002

    with SessionLocal() as db:
        db.add(
            User(
                id="u_disabled",
                username="disabled_user",
                password_hash=hash_password("Disabled@123456"),
                name="Disabled User",
                department_id="dep001",
                status="disabled",
            )
        )
        db.commit()

    disabled = client.post(
        "/api/v1/astron-claw/auth/login",
        json={"username": "disabled_user", "password": "Disabled@123456"},
    )
    assert disabled.status_code == 401
    assert disabled.json()["code"] == 401003


def test_logout_revokes_access_token(client):
    login = client.post(
        "/api/v1/astron-claw/auth/login",
        json={"username": "admin", "password": "Admin@123456"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['data']['accessToken']}"}

    before = client.get("/api/v1/astron-claw/me", headers=headers)
    assert before.status_code == 200

    logout = client.post("/api/v1/astron-claw/auth/logout", headers=headers)
    assert logout.status_code == 200

    after = client.get("/api/v1/astron-claw/me", headers=headers)
    assert after.status_code == 401
    assert after.json()["code"] == 401001


def test_sso_mock_login_returns_business_token_and_permissions(client):
    entry = client.get("/api/v1/astron-claw/auth/sso/login", params={"provider": "customer"})
    assert entry.status_code == 200
    assert "provider=customer" in entry.json()["data"]["loginUrl"]

    callback = client.get(
        "/api/v1/astron-claw/auth/sso/callback",
        params={"provider": "customer", "subject": "admin"},
    )
    assert callback.status_code == 200
    data = callback.json()["data"]
    assert data["accessToken"].startswith("at_")
    assert data["provider"] == "customer"
    assert data["user"]["username"] == "admin"
    assert "agent:create" in data["permissions"]

    headers = {"Authorization": f"Bearer {data['accessToken']}"}
    me = client.get("/api/v1/astron-claw/me", headers=headers)
    assert me.status_code == 200

    logout = client.post("/api/v1/astron-claw/auth/sso/logout", headers=headers)
    assert logout.status_code == 200
    revoked = client.get("/api/v1/astron-claw/me", headers=headers)
    assert revoked.status_code == 401


def test_sso_mock_rejects_unmapped_subject(client):
    callback = client.get(
        "/api/v1/astron-claw/auth/sso/callback",
        params={"provider": "customer", "subject": "missing-subject"},
    )
    assert callback.status_code == 401
    assert callback.json()["code"] == 401001


def test_sso_provider_config_is_masked_and_disabled_provider_blocks_login(client, auth_headers):
    provider = client.post(
        "/api/v1/astron-claw/sso/providers",
        headers=auth_headers,
        json={
            "provider": "corp_oidc",
            "protocol": "oidc",
            "status": "enabled",
            "jitEnabled": True,
            "config": {"clientId": "astron", "clientSecret": "super-secret", "issuer": "https://sso.example.com"},
        },
    )
    assert provider.status_code == 200
    data = provider.json()["data"]
    assert data["config"]["clientSecret"] == "***"
    provider_id = data["id"]

    listed = client.get("/api/v1/astron-claw/sso/providers", headers=auth_headers)
    assert any(item["provider"] == "corp_oidc" and item["config"]["clientSecret"] == "***" for item in listed.json()["data"])

    disabled = client.put(f"/api/v1/astron-claw/sso/providers/{provider_id}", headers=auth_headers, json={"status": "disabled"})
    assert disabled.status_code == 200

    blocked = client.get("/api/v1/astron-claw/auth/sso/login", params={"provider": "corp_oidc"})
    assert blocked.status_code == 401
    assert blocked.json()["code"] == 401003

    audits = client.get("/api/v1/astron-claw/audit/operation-logs", headers=auth_headers, params={"module": "sso"})
    actions = {item["action"] for item in audits.json()["data"]["items"] if item["objectId"] == provider_id}
    assert {"create_provider", "update_provider"} <= actions


def test_password_reset_revokes_sessions_and_writes_audit(client, auth_headers):
    from app.core.security import hash_password
    from app.db import SessionLocal
    from app.models import User

    with SessionLocal() as db:
        db.add(User(id="u_reset", username="reset_user", password_hash=hash_password("OldPass@123"), password_updated_at=datetime.now(timezone.utc), name="Reset User", department_id="dep001", status="active"))
        db.commit()

    login = client.post("/api/v1/astron-claw/auth/login", json={"username": "reset_user", "password": "OldPass@123"})
    assert login.status_code == 200
    old_headers = {"Authorization": f"Bearer {login.json()['data']['accessToken']}"}
    assert client.get("/api/v1/astron-claw/me", headers=old_headers).status_code == 200

    reset = client.post(
        "/api/v1/astron-claw/org/users/u_reset/password-reset",
        headers=auth_headers,
        json={"newPassword": "NewPass@123", "reason": "security reset"},
    )
    assert reset.status_code == 200
    assert reset.json()["data"]["revokedSessions"] == 1
    assert client.get("/api/v1/astron-claw/me", headers=old_headers).status_code == 401

    new_login = client.post("/api/v1/astron-claw/auth/login", json={"username": "reset_user", "password": "NewPass@123"})
    assert new_login.status_code == 200

    audits = client.get("/api/v1/astron-claw/audit/operation-logs", headers=auth_headers, params={"module": "org", "action": "password_reset"})
    assert any(item["objectId"] == "u_reset" for item in audits.json()["data"]["items"])


def test_expired_password_blocks_login_until_reset(client, auth_headers):
    from app.core.security import hash_password
    from app.db import SessionLocal
    from app.models import User

    expired_at = datetime.now(timezone.utc) - timedelta(days=91)
    with SessionLocal() as db:
        db.add(
            User(
                id="u_pwd_expired",
                username="pwd_expired_user",
                password_hash=hash_password("OldPass@123"),
                password_updated_at=expired_at,
                name="Expired Password User",
                department_id="dep001",
                status="active",
            )
        )
        db.commit()

    expired_login = client.post("/api/v1/astron-claw/auth/login", json={"username": "pwd_expired_user", "password": "OldPass@123"})
    assert expired_login.status_code == 401
    assert expired_login.json()["code"] == 401004
    assert expired_login.json()["data"]["userId"] == "u_pwd_expired"

    logs = client.get("/api/v1/astron-claw/audit/login-logs", headers=auth_headers, params={"userId": "u_pwd_expired", "status": "failed"})
    assert any(item["failureReason"] == "password_expired" for item in logs.json()["data"]["items"])

    reset = client.post(
        "/api/v1/astron-claw/org/users/u_pwd_expired/password-reset",
        headers=auth_headers,
        json={"newPassword": "NewPass@123", "reason": "password expired"},
    )
    assert reset.status_code == 200
    assert reset.json()["data"]["passwordUpdatedAt"]

    new_login = client.post("/api/v1/astron-claw/auth/login", json={"username": "pwd_expired_user", "password": "NewPass@123"})
    assert new_login.status_code == 200
    assert new_login.json()["data"]["user"]["passwordUpdatedAt"]


def test_permission_denied_writes_security_audit(client, auth_headers):
    from app.core.security import hash_password
    from app.db import SessionLocal
    from app.models import Role, User, UserRole

    with SessionLocal() as db:
        db.add(Role(id="plain_user", name="普通用户", description="no admin permissions", data_scope={"type": "self", "departmentIds": ["dep002"]}, status="active"))
        db.add(User(id="u_plain", username="plain_user", password_hash=hash_password("Plain@123456"), name="Plain User", department_id="dep002", status="active"))
        db.flush()
        db.add(UserRole(user_id="u_plain", role_id="plain_user"))
        db.commit()

    login = client.post("/api/v1/astron-claw/auth/login", json={"username": "plain_user", "password": "Plain@123456"})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['data']['accessToken']}"}

    denied = client.get("/api/v1/astron-claw/agents", headers=headers)
    assert denied.status_code == 403
    assert denied.json()["code"] == 403001
    assert client.get("/api/v1/astron-claw/roles", headers=headers).status_code == 403
    assert client.get("/api/v1/astron-claw/permissions", headers=headers).status_code == 403
    assert client.get("/api/v1/astron-claw/permission-matrix", headers=headers).status_code == 403
    assert client.get("/api/v1/astron-claw/model-quotas", headers=headers).status_code == 403
    assert client.post("/api/v1/astron-claw/model-quotas", headers=headers, json={"scopeType": "agent", "scopeId": "agt", "modelId": "m001"}).status_code == 403
    assert client.get("/api/v1/astron-claw/model-route-policies", headers=headers).status_code == 403
    assert client.post("/api/v1/astron-claw/model-route-policies", headers=headers, json={"scopeType": "agent", "strategy": "primary_backup"}).status_code == 403
    assert client.post("/api/v1/astron-claw/models/m001/enable", headers=headers).status_code == 403
    assert client.post("/api/v1/astron-claw/models/m001/disable", headers=headers).status_code == 403
    assert client.post("/api/v1/astron-claw/models/m001/probe", headers=headers, json={"latencyMs": 20}).status_code == 403
    assert client.get("/api/v1/astron-claw/cost/export", headers=headers).status_code == 403
    assert client.get("/api/v1/astron-claw/resource-packages", headers=headers).status_code == 403
    assert client.post(
        "/api/v1/astron-claw/resource-packages",
        headers=headers,
        json={"name": "plain package", "packageType": "container", "targetType": "agent", "targetId": "agt"},
    ).status_code == 403
    assert client.get("/api/v1/astron-claw/cost-rules", headers=headers).status_code == 403
    assert client.post(
        "/api/v1/astron-claw/cost-rules",
        headers=headers,
        json={"name": "plain rule", "ruleType": "budget_threshold", "scopeType": "department", "threshold": 0.8},
    ).status_code == 403
    assert client.get("/api/v1/astron-claw/budgets", headers=headers).status_code == 403
    assert client.post(
        "/api/v1/astron-claw/budgets",
        headers=headers,
        json={"name": "plain budget", "scopeType": "department", "scopeId": "dep002", "period": "monthly", "limitAmount": 100},
    ).status_code == 403
    assert client.get("/api/v1/astron-claw/audit/operation-logs", headers=headers).status_code == 403
    assert client.get("/api/v1/astron-claw/audit/login-logs", headers=headers).status_code == 403
    assert client.get("/api/v1/astron-claw/model-call-logs", headers=headers).status_code == 403
    assert client.get("/api/v1/astron-claw/audit/model-call-logs", headers=headers).status_code == 403
    assert client.get("/api/v1/astron-claw/audit/export", headers=headers).status_code == 403
    assert client.get("/api/v1/astron-claw/audit/model-call-logs/export", headers=headers).status_code == 403
    assert client.post("/api/v1/astron-claw/approvals/apr_missing/approve", headers=headers, json={}).status_code == 403
    assert client.post("/api/v1/astron-claw/approvals/apr_missing/reject", headers=headers, json={}).status_code == 403
    assert client.post(
        "/api/v1/astron-claw/skills/import",
        headers=headers,
        json={"name": "plain-skill", "packageName": "plain.skill", "version": "1.0.0"},
    ).status_code == 403
    assert client.post("/api/v1/astron-claw/skills/sk001/review", headers=headers, json={"decision": "approved"}).status_code == 403
    assert client.put("/api/v1/astron-claw/skills/sk001", headers=headers, json={"version": "1.0.1"}).status_code == 403
    assert client.post(
        "/api/v1/astron-claw/skills/sk001/grants",
        headers=headers,
        json={"scopeType": "department", "scopeId": "dep002", "permission": "install"},
    ).status_code == 403
    assert client.get("/api/v1/astron-claw/seat-packages", headers=headers).status_code == 403
    assert client.post("/api/v1/astron-claw/seat-packages", headers=headers, json={"name": "plain seats", "totalCount": 1}).status_code == 403
    assert client.get("/api/v1/astron-claw/seat-assignments", headers=headers).status_code == 403
    assert client.post(
        "/api/v1/astron-claw/seat-assignments",
        headers=headers,
        json={"seatPackageId": "seat_pkg_001", "assigneeType": "user", "assigneeId": "u_plain"},
    ).status_code == 403
    assert client.get("/api/v1/astron-claw/seat-events", headers=headers).status_code == 403
    assert client.get("/api/v1/astron-claw/agents/agt_missing/share-grants", headers=headers).status_code == 403
    assert client.get("/api/v1/astron-claw/sso/providers", headers=headers).status_code == 403
    assert client.post(
        "/api/v1/astron-claw/sso/providers",
        headers=headers,
        json={"provider": "plain_oidc", "protocol": "oidc"},
    ).status_code == 403
    assert client.get("/api/v1/astron-claw/org/positions", headers=headers).status_code == 403
    assert client.post("/api/v1/astron-claw/org/positions", headers=headers, json={"name": "plain position"}).status_code == 403
    assert client.get("/api/v1/astron-claw/org/users", headers=headers).status_code == 403
    assert client.post("/api/v1/astron-claw/org/sync-jobs", headers=headers, json={"source": "plain"}).status_code == 403
    assert client.put("/api/v1/astron-claw/org/users/u_plain/status", headers=headers, json={"status": "disabled"}).status_code == 403
    assert client.post(
        "/api/v1/astron-claw/org/users/u_plain/password-reset",
        headers=headers,
        json={"newPassword": "PlainNew@123"},
    ).status_code == 403
    assert client.post(
        "/api/v1/astron-claw/alert-rules",
        headers=headers,
        json={"name": "plain alert rule", "metricName": "cpu_usage", "threshold": 90},
    ).status_code == 403
    assert client.post(
        "/api/v1/astron-claw/monitor/metrics",
        headers=headers,
        json={"sourceType": "agent", "sourceId": "agt_plain", "metricName": "cpu_usage", "value": 99},
    ).status_code == 403
    assert client.post("/api/v1/astron-claw/alerts", headers=headers, json={"title": "plain alert"}).status_code == 403
    assert client.post("/api/v1/astron-claw/alerts/alt_missing/claim", headers=headers, json={}).status_code == 403
    assert client.post("/api/v1/astron-claw/alerts/alt_missing/process", headers=headers, json={}).status_code == 403
    assert client.post("/api/v1/astron-claw/alerts/alt_missing/transfer", headers=headers, json={"ownerId": "u001"}).status_code == 403
    assert client.post("/api/v1/astron-claw/alerts/alt_missing/suspend", headers=headers, json={}).status_code == 403
    assert client.post("/api/v1/astron-claw/alerts/alt_missing/close", headers=headers, json={"resolution": "done"}).status_code == 403
    assert client.post("/api/v1/astron-claw/ops-tasks", headers=headers, json={"taskType": "restart_agent", "targetType": "agent", "targetId": "agt"}).status_code == 403
    assert client.post("/api/v1/astron-claw/inspection-tasks", headers=headers, json={"name": "plain inspection"}).status_code == 403
    assert client.post(
        "/api/v1/astron-claw/diagnosis-kb",
        headers=headers,
        json={"module": "agent", "symptom": "plain", "reason": "plain", "solution": "plain"},
    ).status_code == 403
    assert client.post("/api/v1/astron-claw/diagnosis-decision-trees", headers=headers, json={"name": "plain tree"}).status_code == 403
    assert client.post(
        "/api/v1/astron-claw/channels",
        headers=headers,
        json={"name": "plain channel", "type": "webhook"},
    ).status_code == 403
    assert client.put("/api/v1/astron-claw/channels/chn001", headers=headers, json={"status": "disabled"}).status_code == 403
    assert client.post("/api/v1/astron-claw/channels/chn001/disable", headers=headers).status_code == 403
    assert client.put("/api/v1/astron-claw/channels/chn001/agents", headers=headers, json={"agentIds": []}).status_code == 403
    assert client.post(
        "/api/v1/astron-claw/business-systems",
        headers=headers,
        json={"name": "plain system", "embedType": "iframe"},
    ).status_code == 403
    assert client.put("/api/v1/astron-claw/business-systems/bs001/agents", headers=headers, json={"agentIds": []}).status_code == 403
    assert client.get("/api/v1/astron-claw/batch-tasks/bat_missing/export", headers=headers).status_code == 403
    assert client.get("/api/v1/astron-claw/inspection-runs/run_missing/export", headers=headers).status_code == 403
    assert client.put(
        "/api/v1/astron-claw/agents/agt_missing/skill-env-vars",
        headers=headers,
        json={"skillId": "sk001", "env": {"API_KEY": "secret"}},
    ).status_code == 403
    assert client.request("DELETE", "/api/v1/astron-claw/agents/agt_missing/skill-env-vars", headers=headers, json={}).status_code == 403
    assert client.put(
        "/api/v1/astron-claw/agents/agt_missing/dev-file/content",
        headers=headers,
        json={"path": "/root/.openclaw/config.yaml", "content": "x"},
    ).status_code == 403
    assert client.post("/api/v1/astron-claw/agents/agt_missing/plugins/astronmem", headers=headers, json={"action": "enable"}).status_code == 403
    assert client.post(
        "/api/v1/astron-claw/agents/agt_missing/crons",
        headers=headers,
        json={"name": "plain cron", "expression": "* * * * *", "task": "noop"},
    ).status_code == 403
    assert client.post("/api/v1/astron-claw/agents/agt_missing/backups", headers=headers).status_code == 403
    assert client.post(
        "/api/v1/astron-claw/agents/agt_missing/backup-restore",
        headers=headers,
        json={"backupTaskId": "bkt_missing"},
    ).status_code == 403
    assert client.delete("/api/v1/astron-claw/agents/agt_missing/backups", headers=headers).status_code == 403

    audits = client.get(
        "/api/v1/astron-claw/audit/operation-logs",
        headers=auth_headers,
        params={"module": "security", "action": "permission_denied", "pageSize": 200},
    )
    assert audits.status_code == 200
    item = next(row for row in audits.json()["data"]["items"] if row["objectId"] == "agent:view")
    assert item["actor"]["id"] == "u_plain"
    assert item["objectType"] == "permission"
    assert item["objectId"] == "agent:view"
    assert item["result"] == "failed"
    assert item["integrityStatus"] == "valid"
    denied_permissions = {row["objectId"] for row in audits.json()["data"]["items"] if row["actor"]["id"] == "u_plain"}
    assert {"agent:view", "agent:batch", "agent:share", "agent:ops", "security:manage", "model:manage", "audit:view", "audit:export", "approval:manage", "skill:manage", "seat:manage", "alert:manage", "ops:manage"} <= denied_permissions


def test_agent_list_respects_department_data_scope(client, auth_headers):
    dep001_agent = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "dep001-agent", "departmentId": "dep001", "ownerId": "u001", "primaryModelId": "m001"},
    )
    dep002_agent = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "dep002-agent", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    assert dep001_agent.status_code == 200
    assert dep002_agent.status_code == 200

    from app.core.security import hash_password
    from app.db import SessionLocal
    from app.models import Role, RolePermission, User, UserRole

    with SessionLocal() as db:
        db.add(Role(id="dep002_viewer", name="Dep002 Viewer", data_scope={"type": "department", "departmentIds": ["dep002"]}, status="active"))
        for permission in ["agent:view", "agent:deploy", "agent:ops", "agent:delete", "model:manage", "agent:batch"]:
            db.add(RolePermission(role_id="dep002_viewer", permission_code=permission))
        db.add(
            User(
                id="u_dep002_viewer",
                username="dep002_viewer",
                password_hash=hash_password("Viewer@123456"),
                name="Dep002 Viewer",
                department_id="dep002",
                status="active",
            )
        )
        db.add(UserRole(user_id="u_dep002_viewer", role_id="dep002_viewer"))
        db.commit()

    login = client.post(
        "/api/v1/astron-claw/auth/login",
        json={"username": "dep002_viewer", "password": "Viewer@123456"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['data']['accessToken']}"}

    scoped = client.get("/api/v1/astron-claw/agents", headers=headers)
    assert scoped.status_code == 200
    agent_ids = {item["id"] for item in scoped.json()["data"]["items"]}
    assert dep002_agent.json()["data"]["id"] in agent_ids
    assert dep001_agent.json()["data"]["id"] not in agent_ids

    conflicting_filter = client.get("/api/v1/astron-claw/agents", headers=headers, params={"departmentId": "dep001"})
    assert conflicting_filter.status_code == 200
    assert conflicting_filter.json()["data"]["items"] == []

    forbidden_detail = client.get(f"/api/v1/astron-claw/agents/{dep001_agent.json()['data']['id']}", headers=headers)
    assert forbidden_detail.status_code == 404

    allowed_detail = client.get(f"/api/v1/astron-claw/agents/{dep002_agent.json()['data']['id']}", headers=headers)
    assert allowed_detail.status_code == 200
    detail_data = allowed_detail.json()["data"]
    required_agent_fields = {
        "name",
        "instanceId",
        "status",
        "version",
        "department",
        "owner",
        "containerCount",
        "skillCount",
        "knowledgeBaseCount",
        "primaryModel",
        "backupModel",
        "cpu",
        "memory",
        "storage",
        "gpu",
        "concurrencyLimit",
        "dailyCallLimit",
        "timeoutMs",
        "currentUsers",
        "maxUsers",
        "qps",
        "createdAt",
        "updatedAt",
    }
    assert required_agent_fields <= set(detail_data["basic"])
    assert detail_data["auditLogs"]
    assert any(item["module"] == "agent" and item["action"] == "create" and item["integrityStatus"] == "valid" for item in detail_data["auditLogs"])
    assert allowed_detail.json()["data"]["basic"]["department"]["id"] == "dep002"

    allowed_logs = client.get(f"/api/v1/astron-claw/agents/{dep002_agent.json()['data']['id']}/logs", headers=headers)
    assert allowed_logs.status_code == 200

    hidden_agent_id = dep001_agent.json()["data"]["id"]
    assert client.get(f"/api/v1/astron-claw/agents/{hidden_agent_id}/logs", headers=headers).status_code == 404
    assert client.post(f"/api/v1/astron-claw/agents/{hidden_agent_id}/stop", headers=headers).status_code == 404
    assert client.post(f"/api/v1/astron-claw/agents/{hidden_agent_id}/sync", headers=headers).status_code == 404
    assert client.put(f"/api/v1/astron-claw/agents/{hidden_agent_id}/model", headers=headers, json={"primaryModelId": "m001"}).status_code == 404
    assert client.put(f"/api/v1/astron-claw/agents/{hidden_agent_id}/runtime-config", headers=headers, json={"timeoutMs": 1000}).status_code == 404
    assert client.delete(f"/api/v1/astron-claw/agents/{hidden_agent_id}", headers=headers).status_code == 404

    forbidden_batch = client.post(
        "/api/v1/astron-claw/batch-tasks",
        headers=headers,
        json={
            "type": "restart",
            "scopeType": "selected",
            "targetIds": [dep002_agent.json()["data"]["id"], hidden_agent_id],
            "strategy": {"batchSize": 10},
        },
    )
    assert forbidden_batch.status_code == 403
    assert hidden_agent_id in forbidden_batch.json()["data"]["unauthorizedTargetIds"]

    scoped_batch = client.post(
        "/api/v1/astron-claw/batch-tasks",
        headers=headers,
        json={
            "type": "restart",
            "scopeType": "filtered",
            "filters": {"departmentId": "dep001"},
            "strategy": {"batchSize": 10},
        },
    )
    assert scoped_batch.status_code == 200
    assert scoped_batch.json()["data"]["total"] == 0


def test_model_list_masks_secret(client, auth_headers):
    response = client.get("/api/v1/astron-claw/models", headers=auth_headers)
    assert response.status_code == 200
    item = response.json()["data"]["items"][0]
    assert "apiKey" not in item
    assert item["apiKeyMasked"]
    assert item["secretRef"].startswith("sec_")
    assert "applicableScenarios" in item
    assert "errorRate" in item


def test_update_model_keeps_api_key_masked(client, auth_headers):
    created = client.post(
        "/api/v1/astron-claw/models",
        headers=auth_headers,
        json={
            "name": "custom-model",
            "provider": "maas",
            "modelKey": "custom-chat",
            "type": "chat",
            "baseUrl": "https://maas.example.com/v1",
            "authType": "api_key",
            "apiKey": "first_secret",
            "unitPrice": 0.01,
            "contextLength": 8192,
            "applicableScenarios": ["claims", "customer_service"],
            "errorRate": 0.02,
            "defaultTimeoutMs": 300000,
        },
    )
    assert created.status_code == 200
    model_id = created.json()["data"]["id"]
    original_secret_ref = created.json()["data"]["secretRef"]
    assert created.json()["data"]["applicableScenarios"] == ["claims", "customer_service"]
    assert created.json()["data"]["errorRate"] == 0.02

    updated = client.put(
        f"/api/v1/astron-claw/models/{model_id}",
        headers=auth_headers,
        json={
            "name": "custom-model-v2",
            "baseUrl": "https://maas.example.com/v2",
            "apiKey": "second_secret",
            "contextLength": 32768,
            "applicableScenarios": ["operations"],
            "errorRate": 0.01,
        },
    )
    assert updated.status_code == 200
    pending = updated.json()["data"]
    assert pending["status"] == "pending_approval"
    assert pending["approvalId"].startswith("apr_")
    assert pending["payload"]["modelId"] == model_id
    assert pending["payload"]["changes"]["name"] == "custom-model-v2"
    assert pending["payload"]["changes"]["baseUrl"] == "https://maas.example.com/v2"
    assert pending["payload"]["apiKeyMasked"]
    assert "second_secret" not in str(pending)

    unchanged = client.get(f"/api/v1/astron-claw/models/{model_id}", headers=auth_headers)
    assert unchanged.status_code == 200
    assert unchanged.json()["data"]["secretRef"] == original_secret_ref

    approved = client.post(f"/api/v1/astron-claw/approvals/{pending['approvalId']}/approve", headers=auth_headers, json={"comment": "rotate key"})
    assert approved.status_code == 200

    detail = client.get(f"/api/v1/astron-claw/models/{model_id}", headers=auth_headers)
    assert detail.status_code == 200
    data = detail.json()["data"]
    assert data["name"] == "custom-model-v2"
    assert data["baseUrl"] == "https://maas.example.com/v2"
    assert data["contextLength"] == 32768
    assert data["applicableScenarios"] == ["operations"]
    assert data["errorRate"] == 0.01
    assert data["secretRef"] != original_secret_ref
    assert data["apiKeyMasked"]
    assert "apiKey" not in data

    secret = client.get(f"/api/v1/astron-claw/models/{model_id}/secret", headers=auth_headers)
    assert secret.status_code == 200
    assert secret.json()["data"]["secretRef"] == data["secretRef"]
    assert "second_secret" not in str(secret.json()["data"])

    sensitive = client.get(
        "/api/v1/astron-claw/audit/sensitive-events",
        headers=auth_headers,
        params={"objectType": "model", "objectId": model_id},
    )
    assert sensitive.status_code == 200
    events = sensitive.json()["data"]["items"]
    event_types = {item["eventType"] for item in events}
    assert {"secret_write", "secret_view"} <= event_types
    assert "first_secret" not in str(events)
    assert "second_secret" not in str(events)


def test_management_api_responses_do_not_leak_raw_secrets(client, auth_headers):
    provider = client.post(
        "/api/v1/astron-claw/sso/providers",
        headers=auth_headers,
        json={
            "provider": "leak_scan_oidc",
            "protocol": "oidc",
            "config": {"clientId": "astron", "clientSecret": "sso_raw_secret_123", "issuer": "https://sso.example.com"},
        },
    )
    assert provider.status_code == 200

    model = client.post(
        "/api/v1/astron-claw/models",
        headers=auth_headers,
        json={
            "name": "leak-scan-model",
            "provider": "maas",
            "modelKey": "leak-scan-chat",
            "type": "chat",
            "baseUrl": "https://leak.example.com/v1",
            "authType": "api_key",
            "apiKey": "model_raw_secret_123",
        },
    )
    assert model.status_code == 200
    model_id = model.json()["data"]["id"]

    agent = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "leak-scan-agent", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001", "skillIds": ["sk001"]},
    )
    assert agent.status_code == 200
    agent_id = agent.json()["data"]["id"]
    client.get(f"/api/v1/astron-claw/agent-tasks/{agent.json()['data']['deployTaskId']}", headers=auth_headers)

    env = client.put(
        f"/api/v1/astron-claw/agents/{agent_id}/skill-env-vars",
        headers=auth_headers,
        json={"skillId": "sk001", "env": {"XFYUN_API_KEY": "skill_env_raw_secret_123"}},
    )
    assert env.status_code == 200

    log = client.post(
        "/api/v1/astron-claw/dev/model-call-logs",
        json={
            "agentId": agent_id,
            "modelId": model_id,
            "latencyMs": 100,
            "inputSummary": "api_secret=model_log_raw_secret_123 token=service_raw_token_123",
            "outputSummary": "bridgeToken=bridge_raw_token_123 password=plain_password_123",
        },
    )
    assert log.status_code == 200

    endpoints = [
        "/api/v1/astron-claw/sso/providers",
        "/api/v1/astron-claw/models",
        f"/api/v1/astron-claw/models/{model_id}",
        f"/api/v1/astron-claw/models/{model_id}/secret",
        f"/api/v1/astron-claw/agents/{agent_id}",
        f"/api/v1/astron-claw/agents/{agent_id}/skill-env-vars",
        f"/api/v1/astron-claw/model-call-logs?agentId={agent_id}",
        "/api/v1/astron-claw/audit/sensitive-events",
    ]
    forbidden_values = [
        "sso_raw_secret_123",
        "model_raw_secret_123",
        "skill_env_raw_secret_123",
        "model_log_raw_secret_123",
        "service_raw_token_123",
        "bridge_raw_token_123",
        "plain_password_123",
    ]
    forbidden_fields = ["bridgeToken", "api_secret"]

    for endpoint in endpoints:
        response = client.get(endpoint, headers=auth_headers)
        assert response.status_code == 200
        payload = json.dumps(response.json(), ensure_ascii=False)
        for raw_secret in forbidden_values:
            assert raw_secret not in payload, endpoint
        for field in forbidden_fields:
            assert field not in payload, endpoint


def test_model_probe_failure_marks_abnormal_and_creates_alert(client, auth_headers):
    created = client.post(
        "/api/v1/astron-claw/models",
        headers=auth_headers,
        json={
            "name": "probe-fail-model",
            "provider": "maas",
            "modelKey": "probe-fail-chat",
            "type": "chat",
            "baseUrl": "https://fail.example.com/v1",
            "authType": "api_key",
            "apiKey": "probe_secret",
            "unitPrice": 0.01,
            "contextLength": 8192,
            "defaultTimeoutMs": 300000,
        },
    )
    assert created.status_code == 200
    model_id = created.json()["data"]["id"]

    probe = client.post(
        f"/api/v1/astron-claw/models/{model_id}/probe",
        headers=auth_headers,
        json={"forceFail": True, "errorMessage": "connect timeout"},
    )
    assert probe.status_code == 200
    data = probe.json()["data"]
    assert data["status"] == "abnormal"
    assert data["probeResult"] == "failed"
    assert data["alertId"].startswith("alt_")

    alert = client.get(f"/api/v1/astron-claw/alerts/{data['alertId']}", headers=auth_headers)
    assert alert.status_code == 200
    assert alert.json()["data"]["sourceType"] == "model"
    assert alert.json()["data"]["errorCode"] == "MODEL_PROBE_FAILED"

    audit_logs = client.get(
        "/api/v1/astron-claw/audit/operation-logs",
        headers=auth_headers,
        params={"module": "model", "action": "probe_failed"},
    )
    assert any(item["objectId"] == model_id for item in audit_logs.json()["data"]["items"])


def test_create_agent_and_query_detail(client, auth_headers):
    before_seats = client.get("/api/v1/astron-claw/seat-packages", headers=auth_headers).json()["data"][0]
    create = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={
            "name": "寿险业务助手",
            "departmentId": "dep002",
            "ownerId": "u001",
            "primaryModelId": "m001",
            "backupModelId": "m002",
            "resourceSpec": {"cpu": 2, "memory": "4Gi", "storage": "20Gi", "gpu": 0},
            "skillIds": ["sk001"],
            "knowledgeBaseIds": ["kb001"],
        },
    )
    assert create.status_code == 200
    data = create.json()["data"]
    assert data["status"] == "deploying"
    assert data["botId"].startswith("agt_")

    task = client.get(f"/api/v1/astron-claw/agent-tasks/{data['deployTaskId']}", headers=auth_headers)
    assert task.status_code == 200
    assert task.json()["data"]["status"] == "success"
    assert task.json()["data"]["progress"] == 100

    detail = client.get(f"/api/v1/astron-claw/agents/{data['id']}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["basic"]["name"] == "寿险业务助手"
    assert detail.json()["data"]["basic"]["status"] == "running"
    assert detail.json()["data"]["basic"]["instanceId"].startswith("sandbox-")
    after_seats = client.get("/api/v1/astron-claw/seat-packages", headers=auth_headers).json()["data"][0]
    assert after_seats["usedCount"] == before_seats["usedCount"] + 1


def test_create_agent_binds_message_channels(client, auth_headers):
    channel = client.post(
        "/api/v1/astron-claw/channels",
        headers=auth_headers,
        json={"name": "创建绑定渠道", "type": "webhook", "callbackUrl": "https://example.com/create-bind"},
    )
    assert channel.status_code == 200
    channel_id = channel.json()["data"]["id"]

    create = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={
            "name": "带渠道助手",
            "departmentId": "dep002",
            "ownerId": "u001",
            "primaryModelId": "m001",
            "messageChannelIds": [channel_id],
        },
    )
    assert create.status_code == 200
    agent_id = create.json()["data"]["id"]

    binds = client.get(f"/api/v1/astron-claw/channels/{channel_id}/agents", headers=auth_headers)
    assert binds.status_code == 200
    assert any(item["agentId"] == agent_id and item["status"] == "active" for item in binds.json()["data"]["items"])

    audits = client.get("/api/v1/astron-claw/channel-audit-logs", headers=auth_headers, params={"action": "bind_agent_on_create"})
    assert any(item["channelId"] == channel_id and item["detail"]["agentId"] == agent_id for item in audits.json()["data"]["items"])


def test_create_agent_precheck_rejects_disabled_model_or_channel_without_consuming_seat(client, auth_headers):
    before_seats = next(item for item in client.get("/api/v1/astron-claw/seat-packages", headers=auth_headers).json()["data"] if item["id"] == "seat_pkg_001")
    disabled_model = client.post("/api/v1/astron-claw/models/m001/disable", headers=auth_headers, json={})
    assert disabled_model.status_code == 200

    rejected_model = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "禁用模型助手", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    assert rejected_model.status_code == 422
    assert rejected_model.json()["data"]["reason"] == "model_not_enabled"

    client.post("/api/v1/astron-claw/models/m001/enable", headers=auth_headers, json={})
    disabled_channel = client.post(
        "/api/v1/astron-claw/channels",
        headers=auth_headers,
        json={"name": "禁用渠道", "type": "webhook", "status": "disabled"},
    )
    assert disabled_channel.status_code == 200
    rejected_channel = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={
            "name": "禁用渠道助手",
            "departmentId": "dep002",
            "ownerId": "u001",
            "primaryModelId": "m001",
            "messageChannelIds": [disabled_channel.json()["data"]["id"]],
        },
    )
    assert rejected_channel.status_code == 422
    assert rejected_channel.json()["data"]["reason"] == "channel_not_enabled"

    after_seats = next(item for item in client.get("/api/v1/astron-claw/seat-packages", headers=auth_headers).json()["data"] if item["id"] == "seat_pkg_001")
    assert after_seats["usedCount"] == before_seats["usedCount"]


def test_archive_agent_reclaims_seat_and_disables_integrations(client, auth_headers):
    before_pkg = next(item for item in client.get("/api/v1/astron-claw/seat-packages", headers=auth_headers).json()["data"] if item["id"] == "seat_pkg_001")
    channel = client.post(
        "/api/v1/astron-claw/channels",
        headers=auth_headers,
        json={"name": "归档释放渠道", "type": "webhook", "callbackUrl": "https://example.com/archive-release"},
    )
    channel_id = channel.json()["data"]["id"]
    create = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={
            "name": "归档释放助手",
            "departmentId": "dep002",
            "ownerId": "u001",
            "primaryModelId": "m001",
            "messageChannelIds": [channel_id],
        },
    )
    assert create.status_code == 200
    agent_id = create.json()["data"]["id"]

    system = client.post(
        "/api/v1/astron-claw/business-systems",
        headers=auth_headers,
        json={"name": "归档释放系统", "embedType": "iframe", "ssoMode": "backend"},
    )
    system_id = system.json()["data"]["id"]
    bind_system = client.put(
        f"/api/v1/astron-claw/business-systems/{system_id}/agents",
        headers=auth_headers,
        json={"agentIds": [agent_id]},
    )
    assert bind_system.status_code == 200

    stop = client.post(f"/api/v1/astron-claw/agents/{agent_id}/stop", headers=auth_headers, json={})
    assert stop.status_code == 200
    assert client.get(f"/api/v1/astron-claw/agent-tasks/{stop.json()['data']['taskId']}", headers=auth_headers).status_code == 200

    archived = client.post(f"/api/v1/astron-claw/agents/{agent_id}/archive", headers=auth_headers, json={"reason": "retired"})
    assert archived.status_code == 200
    released = archived.json()["data"]["releasedResources"]
    assert released["reclaimedSeats"][0]["agentId"] == agent_id
    assert released["disabledChannelBindings"] == [{"channelId": channel_id, "agentId": agent_id}]
    assert released["disabledBusinessSystemGrants"] == [{"businessSystemId": system_id, "agentId": agent_id}]

    after_pkg = next(item for item in client.get("/api/v1/astron-claw/seat-packages", headers=auth_headers).json()["data"] if item["id"] == "seat_pkg_001")
    assert after_pkg["usedCount"] == before_pkg["usedCount"]

    channel_binds = client.get(f"/api/v1/astron-claw/channels/{channel_id}/agents", headers=auth_headers)
    archived_bind = next(item for item in channel_binds.json()["data"]["items"] if item["agentId"] == agent_id)
    assert archived_bind["status"] == "disabled"

    system_grants = client.get(f"/api/v1/astron-claw/business-systems/{system_id}/agents", headers=auth_headers)
    archived_grant = next(item for item in system_grants.json()["data"]["items"] if item["agentId"] == agent_id)
    assert archived_grant["status"] == "disabled"

    seat_events = client.get("/api/v1/astron-claw/seat-events", headers=auth_headers, params={"eventType": "reclaim", "assigneeId": agent_id})
    assert any(item["reason"] == "agent archived" for item in seat_events.json()["data"]["items"])


def test_agent_versions_state_events_and_rollback(client, auth_headers):
    create = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "版本生命周期助手", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    assert create.status_code == 200
    agent_id = create.json()["data"]["id"]
    deploy_task = create.json()["data"]["deployTaskId"]
    assert client.get(f"/api/v1/astron-claw/agent-tasks/{deploy_task}", headers=auth_headers).status_code == 200

    versions = client.get(f"/api/v1/astron-claw/agents/{agent_id}/versions", headers=auth_headers)
    assert versions.status_code == 200
    assert any(item["version"] == "1.0.0" for item in versions.json()["data"]["items"])

    upgrade = client.post(
        f"/api/v1/astron-claw/agents/{agent_id}/upgrade",
        headers=auth_headers,
        json={"targetVersion": "1.1.0", "reason": "灰度升级"},
    )
    assert upgrade.status_code == 200
    assert upgrade.json()["data"]["targetVersion"] == "1.1.0"
    upgrade_task = upgrade.json()["data"]["taskId"]
    upgraded_task = client.get(f"/api/v1/astron-claw/agent-tasks/{upgrade_task}", headers=auth_headers)
    assert upgraded_task.status_code == 200
    assert upgraded_task.json()["data"]["status"] == "success"

    detail = client.get(f"/api/v1/astron-claw/agents/{agent_id}", headers=auth_headers)
    assert detail.json()["data"]["basic"]["version"] == "1.1.0"
    version_items = detail.json()["data"]["versionHistory"]
    assert {"1.0.0", "1.1.0"} <= {item["version"] for item in version_items}

    events = client.get(f"/api/v1/astron-claw/agents/{agent_id}/state-events", headers=auth_headers)
    assert events.status_code == 200
    reasons = {item["reason"] for item in events.json()["data"]["items"]}
    assert {"deploy_completed", "灰度升级", "upgrade_completed"} <= reasons

    rollback = client.post(
        f"/api/v1/astron-claw/agents/{agent_id}/rollback",
        headers=auth_headers,
        json={"version": "1.0.0", "reason": "回滚到稳定版本"},
    )
    assert rollback.status_code == 200
    assert rollback.json()["data"]["version"] == "1.0.0"
    assert rollback.json()["data"]["rollbackFrom"] == "1.1.0"

    versions_after = client.get(f"/api/v1/astron-claw/agents/{agent_id}/versions", headers=auth_headers)
    rollback_version = next(item for item in versions_after.json()["data"]["items"] if item["rollbackFrom"] == "1.1.0")
    assert rollback_version["version"] == "1.0.0"

    audit_logs = client.get("/api/v1/astron-claw/audit/operation-logs", headers=auth_headers, params={"module": "agent", "action": "rollback"})
    assert any(item["objectId"] == agent_id for item in audit_logs.json()["data"]["items"])


def test_violation_offline_keeps_evidence_and_approval_record(client, auth_headers):
    create = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "违规下线助手", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    assert create.status_code == 200
    agent_id = create.json()["data"]["id"]
    client.get(f"/api/v1/astron-claw/agent-tasks/{create.json()['data']['deployTaskId']}", headers=auth_headers)

    offline = client.post(
        f"/api/v1/astron-claw/agents/{agent_id}/violation-offline",
        headers=auth_headers,
        json={"reason": "命中违规提示词", "evidence": [{"type": "model_call_log", "id": "mcl_violation_001"}]},
    )
    assert offline.status_code == 200
    data = offline.json()["data"]
    assert data["approvalId"].startswith("apr_")
    assert data["evidence"]["riskLevel"] == "critical"
    assert data["evidence"]["evidence"] == [{"type": "model_call_log", "id": "mcl_violation_001"}]

    detail = client.get(f"/api/v1/astron-claw/agents/{agent_id}", headers=auth_headers)
    assert detail.json()["data"]["basic"]["status"] == "violation_offline"

    approval = client.get(f"/api/v1/astron-claw/approvals/{data['approvalId']}", headers=auth_headers)
    assert approval.status_code == 200
    approval_data = approval.json()["data"]
    assert approval_data["type"] == "violation_offline"
    assert approval_data["riskLevel"] == "critical"
    assert approval_data["status"] == "approved"
    assert approval_data["payload"]["agentId"] == agent_id
    assert approval_data["steps"][0]["decision"] == "approved"

    events = client.get(f"/api/v1/astron-claw/agents/{agent_id}/state-events", headers=auth_headers)
    assert any(item["toStatus"] == "violation_offline" and item["reason"] == "命中违规提示词" for item in events.json()["data"]["items"])

    audits = client.get("/api/v1/astron-claw/audit/operation-logs", headers=auth_headers, params={"module": "agent", "action": "violation-offline"})
    assert any(item["objectId"] == agent_id and item["integrityStatus"] == "valid" for item in audits.json()["data"]["items"])


def test_agent_runtime_config_history_and_logs(client, auth_headers):
    create = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "远程运维助手", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    assert create.status_code == 200
    agent_id = create.json()["data"]["id"]
    client.get(f"/api/v1/astron-claw/agent-tasks/{create.json()['data']['deployTaskId']}", headers=auth_headers)

    update = client.put(
        f"/api/v1/astron-claw/agents/{agent_id}/runtime-config",
        headers=auth_headers,
        json={
            "concurrencyLimit": 12,
            "dailyCallLimit": 888,
            "timeoutMs": 120000,
            "resourceSpec": {"cpu": 4, "memory": "8Gi", "storage": "40Gi", "gpu": 0},
            "memoryPolicy": "department",
            "restartAfterUpdated": True,
        },
    )
    assert update.status_code == 200
    updated = update.json()["data"]
    assert updated["configVersion"] == 1
    assert updated["restartTaskId"].startswith("task_")
    assert updated["runtimeConfig"]["config"]["concurrencyLimit"] == 12

    config = client.get(f"/api/v1/astron-claw/agents/{agent_id}/runtime-config", headers=auth_headers)
    assert config.status_code == 200
    config_data = config.json()["data"]
    assert config_data["current"]["timeoutMs"] == 120000
    assert config_data["history"]["items"][0]["restartRequired"] is True

    first_log = client.post(
        "/api/v1/astron-claw/dev/agent-logs",
        json={"agentId": agent_id, "logType": "runtime", "level": "error", "message": "proxy restart failed", "traceId": "tr-001"},
    )
    second_log = client.post(
        "/api/v1/astron-claw/dev/agent-logs",
        json={"agentId": agent_id, "logType": "deploy", "level": "info", "message": "deployment success"},
    )
    assert first_log.status_code == 200
    assert second_log.status_code == 200

    logs = client.get(
        f"/api/v1/astron-claw/agents/{agent_id}/logs",
        headers=auth_headers,
        params={"logType": "runtime", "level": "error", "keyword": "restart"},
    )
    assert logs.status_code == 200
    items = logs.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["traceId"] == "tr-001"
    assert items[0]["message"] == "proxy restart failed"


@pytest.mark.parametrize(
    ("failure_mode", "expected_code"),
    [
        ("300003", "502003"),
        ("timeout", "502001"),
    ],
)
def test_agent_deploy_failure_marks_abnormal_and_creates_alert(client, auth_headers, failure_mode, expected_code):
    create = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={
            "name": f"部署失败助手-{failure_mode}",
            "departmentId": "dep002",
            "ownerId": "u001",
            "primaryModelId": "m001",
            "resourceSpec": {"cpu": 2, "memory": "4Gi", "storage": "20Gi", "gpu": 0, "_mockDeployFailure": failure_mode},
        },
    )
    assert create.status_code == 200
    data = create.json()["data"]

    task = client.get(f"/api/v1/astron-claw/agent-tasks/{data['deployTaskId']}", headers=auth_headers)
    assert task.status_code == 200
    task_data = task.json()["data"]
    assert task_data["status"] == "failed"
    assert task_data["phase"] == "deploy"
    assert task_data["progress"] == 100
    assert task_data["errorCode"] == expected_code
    assert task_data["retryAdvice"]

    detail = client.get(f"/api/v1/astron-claw/agents/{data['id']}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["basic"]["status"] == "abnormal"

    alerts = client.get(
        "/api/v1/astron-claw/alerts",
        headers=auth_headers,
        params={"sourceType": "agent", "sourceId": data["id"]},
    )
    assert alerts.status_code == 200
    assert any(item["errorCode"] == expected_code and item["category"] == "task_failure" for item in alerts.json()["data"]["items"])

    audit_logs = client.get(
        "/api/v1/astron-claw/audit/operation-logs",
        headers=auth_headers,
        params={"module": "agent_task", "action": "failed"},
    )
    assert audit_logs.status_code == 200
    assert any(item["objectId"] == data["deployTaskId"] and item["result"] == "failed" for item in audit_logs.json()["data"]["items"])


def test_bridge_token_failure_does_not_create_deploy_task_or_consume_seat(client, auth_headers):
    before_seats = next(item for item in client.get("/api/v1/astron-claw/seat-packages", headers=auth_headers).json()["data"] if item["id"] == "seat_pkg_001")
    create = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={
            "name": "bridge-token-failure-agent",
            "departmentId": "dep002",
            "ownerId": "u001",
            "primaryModelId": "m001",
            "resourceSpec": {"cpu": 2, "memory": "4Gi", "storage": "20Gi", "gpu": 0, "_mockBridgeFailure": True},
        },
    )
    assert create.status_code == 502
    assert create.json()["code"] == 502001
    assert create.json()["data"] == {"phase": "bridge_token", "deployTaskCreated": False}

    agents = client.get("/api/v1/astron-claw/agents", headers=auth_headers, params={"keyword": "bridge-token-failure-agent"})
    assert agents.status_code == 200
    assert agents.json()["data"]["items"] == []

    after_seats = next(item for item in client.get("/api/v1/astron-claw/seat-packages", headers=auth_headers).json()["data"] if item["id"] == "seat_pkg_001")
    assert after_seats["usedCount"] == before_seats["usedCount"]

    audits = client.get("/api/v1/astron-claw/audit/operation-logs", headers=auth_headers, params={"module": "agent", "action": "create_failed"})
    assert audits.status_code == 200
    assert any(item["result"] == "failed" and item["errorMessage"] == "bridge unavailable" for item in audits.json()["data"]["items"])


def test_deploy_installs_bound_skills_and_detects_runtime_drift(client, auth_headers):
    skill = client.post(
        "/api/v1/astron-claw/skills",
        headers=auth_headers,
        json={"name": "投保校验技能", "packageName": "com.astron.skill.policy-check", "version": "1.0.0"},
    )
    assert skill.status_code == 200
    skill_id = skill.json()["data"]["id"]

    review = client.post(f"/api/v1/astron-claw/skills/{skill_id}/review", headers=auth_headers, json={"approved": True})
    assert review.status_code == 200

    create = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={
            "name": "技能部署助手",
            "departmentId": "dep002",
            "ownerId": "u001",
            "primaryModelId": "m001",
            "skillIds": [skill_id],
        },
    )
    assert create.status_code == 200
    data = create.json()["data"]

    before_task = client.get(f"/api/v1/astron-claw/agents/{data['id']}/runtime-skills", headers=auth_headers)
    assert before_task.status_code == 200
    assert before_task.json()["data"]["items"][0]["status"] == "pending"
    assert before_task.json()["data"]["items"][0]["drift"] is True

    task = client.get(f"/api/v1/astron-claw/agent-tasks/{data['deployTaskId']}", headers=auth_headers)
    assert task.status_code == 200
    assert task.json()["data"]["status"] == "success"

    runtime = client.get(f"/api/v1/astron-claw/agents/{data['id']}/runtime-skills", headers=auth_headers)
    assert runtime.status_code == 200
    item = runtime.json()["data"]["items"][0]
    assert item["status"] == "installed"
    assert item["installedVersion"] == "1.0.0"
    assert item["expectedVersion"] == "1.0.0"
    assert item["drift"] is False

    update = client.put(f"/api/v1/astron-claw/skills/{skill_id}", headers=auth_headers, json={"version": "2.0.0"})
    assert update.status_code == 200

    drift = client.get(f"/api/v1/astron-claw/agents/{data['id']}/runtime-skills", headers=auth_headers)
    assert drift.status_code == 200
    drift_item = drift.json()["data"]["items"][0]
    assert drift_item["installedVersion"] == "1.0.0"
    assert drift_item["expectedVersion"] == "2.0.0"
    assert drift_item["drift"] is True


def test_deploy_skill_partial_failure_keeps_failed_skill_detail(client, auth_headers):
    first = client.post(
        "/api/v1/astron-claw/skills",
        headers=auth_headers,
        json={"name": "可安装技能", "packageName": "com.astron.skill.ok", "version": "1.0.0"},
    )
    second = client.post(
        "/api/v1/astron-claw/skills",
        headers=auth_headers,
        json={"name": "失败技能", "packageName": "com.astron.skill.fail", "version": "1.0.0"},
    )
    first_id = first.json()["data"]["id"]
    second_id = second.json()["data"]["id"]
    assert client.post(f"/api/v1/astron-claw/skills/{first_id}/review", headers=auth_headers, json={"approved": True}).status_code == 200
    assert client.post(f"/api/v1/astron-claw/skills/{second_id}/review", headers=auth_headers, json={"approved": True}).status_code == 200

    create = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={
            "name": "技能部分失败助手",
            "departmentId": "dep002",
            "ownerId": "u001",
            "primaryModelId": "m001",
            "skillIds": [first_id, second_id],
            "resourceSpec": {"cpu": 2, "memory": "4Gi", "storage": "20Gi", "gpu": 0, "_mockSkillInstallFailure": [second_id]},
        },
    )
    assert create.status_code == 200
    data = create.json()["data"]

    task = client.get(f"/api/v1/astron-claw/agent-tasks/{data['deployTaskId']}", headers=auth_headers)
    assert task.status_code == 200
    task_data = task.json()["data"]
    assert task_data["status"] == "failed"
    assert task_data["phase"] == "skill_install"
    assert task_data["errorCode"] == "SKILL_INSTALL_FAILED"
    assert second_id in task_data["errorMessage"]

    detail = client.get(f"/api/v1/astron-claw/agents/{data['id']}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["basic"]["status"] == "abnormal"

    runtime = client.get(f"/api/v1/astron-claw/agents/{data['id']}/runtime-skills", headers=auth_headers)
    assert runtime.status_code == 200
    by_skill = {item["skillId"]: item for item in runtime.json()["data"]["items"]}
    assert by_skill[first_id]["status"] == "installed"
    assert by_skill[first_id]["drift"] is False
    assert by_skill[second_id]["status"] == "failed"
    assert by_skill[second_id]["drift"] is True
    assert by_skill[second_id]["errorMessage"] == "skill install failed"


def test_skill_list_filters_and_bound_agent_count(client, auth_headers):
    skill = client.post(
        "/api/v1/astron-claw/skills",
        headers=auth_headers,
        json={
            "name": "保单影像解析",
            "packageName": "com.astron.skill.policy-ocr",
            "source": "custom",
            "category": "ocr",
            "version": "1.0.0",
        },
    )
    assert skill.status_code == 200
    skill_id = skill.json()["data"]["id"]
    assert client.post(f"/api/v1/astron-claw/skills/{skill_id}/review", headers=auth_headers, json={"approved": True}).status_code == 200

    create = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={
            "name": "影像解析助手",
            "departmentId": "dep002",
            "ownerId": "u001",
            "primaryModelId": "m001",
            "skillIds": [skill_id],
        },
    )
    assert create.status_code == 200

    listed = client.get(
        "/api/v1/astron-claw/skills",
        headers=auth_headers,
        params={"keyword": "policy-ocr", "status": "enabled", "source": "custom", "category": "ocr"},
    )
    assert listed.status_code == 200
    items = listed.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["id"] == skill_id
    assert items[0]["creator"]["name"] == "系统管理员"
    assert items[0]["boundAgentCount"] == 1


def test_skill_scan_versions_reviews_and_grants_control_install(client, auth_headers):
    blocked = client.post(
        "/api/v1/astron-claw/skills/import",
        headers=auth_headers,
        json={
            "name": "高风险离线技能",
            "packageName": "com.astron.skill.risky-offline",
            "source": "offline",
            "version": "1.0.0",
            "forceScanFail": True,
            "scanError": "malware signature detected",
        },
    )
    assert blocked.status_code == 200
    blocked_data = blocked.json()["data"]
    assert blocked_data["status"] == "disabled"
    assert blocked_data["scanStatus"] == "failed"

    blocked_review = client.post(
        f"/api/v1/astron-claw/skills/{blocked_data['id']}/review",
        headers=auth_headers,
        json={"decision": "approved"},
    )
    assert blocked_review.status_code == 409

    skill = client.post(
        "/api/v1/astron-claw/skills/import",
        headers=auth_headers,
        json={
            "name": "受限核保技能",
            "packageName": "com.astron.skill.restricted-underwrite",
            "source": "url",
            "packageUrl": "https://example.com/restricted-underwrite.zip",
            "version": "1.0.0",
            "allowedRoles": ["ops_viewer"],
        },
    )
    assert skill.status_code == 200
    skill_id = skill.json()["data"]["id"]
    assert skill.json()["data"]["scanStatus"] == "passed"

    versions = client.get(f"/api/v1/astron-claw/skills/{skill_id}/versions", headers=auth_headers)
    assert versions.status_code == 200
    assert versions.json()["data"]["items"][0]["scanStatus"] == "passed"

    review = client.post(
        f"/api/v1/astron-claw/skills/{skill_id}/review",
        headers=auth_headers,
        json={"decision": "approved", "comment": "scan passed"},
    )
    assert review.status_code == 200
    review_id = review.json()["data"]["reviewId"]

    reviews = client.get(f"/api/v1/astron-claw/skills/{skill_id}/reviews", headers=auth_headers)
    assert reviews.status_code == 200
    assert any(item["id"] == review_id and item["decision"] == "approved" for item in reviews.json()["data"]["items"])

    agent = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "受限技能安装助手", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    assert agent.status_code == 200
    agent_id = agent.json()["data"]["id"]

    forbidden = client.post(f"/api/v1/astron-claw/agents/{agent_id}/skills/{skill_id}/install", headers=auth_headers)
    assert forbidden.status_code == 403
    denied = client.get(
        "/api/v1/astron-claw/audit/operation-logs",
        headers=auth_headers,
        params={"module": "security", "action": "permission_denied", "pageSize": 100},
    )
    assert denied.status_code == 200
    assert any(row["actor"]["id"] == "u001" and row["objectId"] == "skill:install" for row in denied.json()["data"]["items"])

    grant = client.post(
        f"/api/v1/astron-claw/skills/{skill_id}/grants",
        headers=auth_headers,
        json={"scopeType": "role", "scopeId": "super_admin", "permission": "install"},
    )
    assert grant.status_code == 200

    grants = client.get(f"/api/v1/astron-claw/skills/{skill_id}/grants", headers=auth_headers)
    assert grants.status_code == 200
    assert any(item["scopeId"] == "super_admin" for item in grants.json()["data"]["items"])

    installed = client.post(f"/api/v1/astron-claw/agents/{agent_id}/skills/{skill_id}/install", headers=auth_headers)
    assert installed.status_code == 200
    assert installed.json()["data"]["status"] == "installed"

    audits = client.get("/api/v1/astron-claw/audit/operation-logs", headers=auth_headers, params={"module": "skill", "action": "grant"})
    assert audits.status_code == 200
    assert any(item["objectId"] == skill_id for item in audits.json()["data"]["items"])


def test_skill_env_vars_are_upserted_masked_and_can_restart_agent(client, auth_headers):
    create = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={
            "name": "环境变量助手",
            "departmentId": "dep002",
            "ownerId": "u001",
            "primaryModelId": "m001",
            "skillIds": ["sk001"],
        },
    )
    assert create.status_code == 200
    agent_id = create.json()["data"]["id"]

    first = client.put(
        f"/api/v1/astron-claw/agents/{agent_id}/skill-env-vars",
        headers=auth_headers,
        json={"skillId": "sk001", "env": {"XFYUN_API_KEY": "first-secret"}, "restartAfterUpdated": False},
    )
    assert first.status_code == 200

    second = client.put(
        f"/api/v1/astron-claw/agents/{agent_id}/skill-env-vars",
        headers=auth_headers,
        json={"skillId": "sk001", "env": {"XFYUN_API_KEY": "second-secret"}, "restartAfterUpdated": True},
    )
    assert second.status_code == 200
    assert second.json()["data"]["restartAfterUpdated"] is True
    restart_task_id = second.json()["data"]["restartTaskId"]
    assert restart_task_id.startswith("task_")

    rows = client.get(f"/api/v1/astron-claw/agents/{agent_id}/skill-env-vars", headers=auth_headers)
    assert rows.status_code == 200
    items = rows.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["envName"] == "XFYUN_API_KEY"
    assert "***" in items[0]["maskedValue"]
    assert "first-secret" not in items[0]["maskedValue"]
    assert "second-secret" not in items[0]["maskedValue"]

    task = client.get(f"/api/v1/astron-claw/agent-tasks/{restart_task_id}", headers=auth_headers)
    assert task.status_code == 200
    assert task.json()["data"]["status"] == "success"

    deleted = client.request(
        "DELETE",
        f"/api/v1/astron-claw/agents/{agent_id}/skill-env-vars",
        headers=auth_headers,
        json={"skillId": "sk001", "envNames": ["XFYUN_API_KEY"]},
    )
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted"] == [{"skillId": "sk001", "envName": "XFYUN_API_KEY"}]
    assert client.get(f"/api/v1/astron-claw/agents/{agent_id}/skill-env-vars", headers=auth_headers).json()["data"]["items"] == []


def test_cron_route_is_not_captured_by_lifecycle(client, auth_headers):
    create = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "cron-test", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    agent_id = create.json()["data"]["id"]

    cron = client.post(
        f"/api/v1/astron-claw/agents/{agent_id}/crons",
        headers=auth_headers,
        json={
            "name": "每日晨报",
            "expression": "0 8 * * *",
            "type": "cron",
            "task": "推送今日晨报",
            "timeZone": "Asia/Shanghai",
            "channel": "openclaw-weixin",
        },
    )
    assert cron.status_code == 200
    assert cron.json()["data"]["name"] == "每日晨报"
    assert cron.json()["data"]["proxyCronId"].startswith("proxy_cron")


def test_cron_proxy_id_reused_and_agent_scope_enforced(client, auth_headers):
    first = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "cron-scope-a", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    second = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "cron-scope-b", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    first_id = first.json()["data"]["id"]
    second_id = second.json()["data"]["id"]

    missing_agent = client.post(
        "/api/v1/astron-claw/agents/missing/crons",
        headers=auth_headers,
        json={"name": "bad", "expression": "* * * * *", "task": "noop"},
    )
    assert missing_agent.status_code == 404

    created = client.post(
        f"/api/v1/astron-claw/agents/{first_id}/crons",
        headers=auth_headers,
        json={"name": "巡检", "expression": "*/5 * * * *", "task": "health check", "timeZone": "Asia/Shanghai"},
    )
    assert created.status_code == 200
    cron_data = created.json()["data"]
    cron_id = cron_data["id"]
    proxy_cron_id = cron_data["proxyCronId"]

    updated = client.put(
        f"/api/v1/astron-claw/agents/{first_id}/crons/{cron_id}",
        headers=auth_headers,
        json={"name": "巡检更新", "expression": "*/10 * * * *", "status": "disabled"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["proxyCronId"] == proxy_cron_id
    assert updated.json()["data"]["status"] == "disabled"

    cross_update = client.put(
        f"/api/v1/astron-claw/agents/{second_id}/crons/{cron_id}",
        headers=auth_headers,
        json={"name": "cross"},
    )
    assert cross_update.status_code == 404

    cross_runs = client.get(f"/api/v1/astron-claw/agents/{second_id}/crons/{cron_id}/runs", headers=auth_headers)
    assert cross_runs.status_code == 404

    runs = client.get(f"/api/v1/astron-claw/agents/{first_id}/crons/{cron_id}/runs", headers=auth_headers)
    assert runs.status_code == 200
    assert runs.json()["data"]["items"] == []

    cross_delete = client.delete(f"/api/v1/astron-claw/agents/{second_id}/crons/{cron_id}", headers=auth_headers)
    assert cross_delete.status_code == 404

    deleted = client.delete(f"/api/v1/astron-claw/agents/{first_id}/crons/{cron_id}", headers=auth_headers)
    assert deleted.status_code == 200

    logs = client.get("/api/v1/astron-claw/audit/operation-logs", headers=auth_headers, params={"module": "cron"})
    actions = {item["action"] for item in logs.json()["data"]["items"] if item["objectId"] == cron_id}
    assert {"create", "update", "delete"} <= actions


def test_team_routes_validate_agent_and_return_empty_contract(client, auth_headers):
    create = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "team-agent", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    agent_id = create.json()["data"]["id"]

    missing = client.get("/api/v1/astron-claw/agents/missing/teams", headers=auth_headers, params={"sessionId": "s001"})
    assert missing.status_code == 404

    teams = client.get(f"/api/v1/astron-claw/agents/{agent_id}/teams", headers=auth_headers, params={"sessionId": "s001"})
    assert teams.status_code == 200
    teams_data = teams.json()["data"]
    assert teams_data["sessionKey"] == "agent:main:main:s001"
    assert teams_data["items"] == []
    assert teams_data["proxyCode"] == 0
    assert teams_data["empty"] is True

    for kind in ["progress", "outputs", "result"]:
        response = client.get(
            f"/api/v1/astron-claw/agents/{agent_id}/teams/team001/{kind}",
            headers=auth_headers,
            params={"sessionId": "s001"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["teamId"] == "team001"
        assert data["kind"] == kind
        assert data["sessionKey"] == "agent:main:main:s001"
        assert data["items"] == []
        assert data["empty"] is True


def test_backup_restore_task_flow(client, auth_headers):
    create = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "backup-agent", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    agent_id = create.json()["data"]["id"]
    client.get(f"/api/v1/astron-claw/agent-tasks/{create.json()['data']['deployTaskId']}", headers=auth_headers)

    backup = client.post(f"/api/v1/astron-claw/agents/{agent_id}/backups", headers=auth_headers)
    assert backup.status_code == 200
    backup_data = backup.json()["data"]
    assert backup_data["type"] == "backup"
    assert backup_data["status"] == "running"
    assert backup_data["proxyTaskId"].startswith("proxy_backup")

    backup_status = client.get(
        f"/api/v1/astron-claw/agents/{agent_id}/backups/{backup_data['taskId']}",
        headers=auth_headers,
    )
    assert backup_status.status_code == 200
    assert backup_status.json()["data"]["status"] == "success"
    assert backup_status.json()["data"]["phase"] == "completed"
    assert backup_status.json()["data"]["endedAt"]

    restore = client.post(
        f"/api/v1/astron-claw/agents/{agent_id}/backup-restore",
        headers=auth_headers,
        json={"backupTaskId": backup_data["taskId"]},
    )
    assert restore.status_code == 200
    restore_data = restore.json()["data"]
    assert restore_data["type"] == "restore"
    assert restore_data["proxyTaskId"].startswith("proxy_restore")

    restore_status = client.get(
        f"/api/v1/astron-claw/agents/{agent_id}/backup-restore/{restore_data['taskId']}",
        headers=auth_headers,
    )
    assert restore_status.status_code == 200
    assert restore_status.json()["data"]["status"] == "success"

    deleted = client.delete(f"/api/v1/astron-claw/agents/{agent_id}/backups", headers=auth_headers)
    assert deleted.status_code == 200


def test_backup_restore_validates_agent_and_backup_task(client, auth_headers):
    missing_agent = client.post("/api/v1/astron-claw/agents/missing/backups", headers=auth_headers)
    assert missing_agent.status_code == 404

    first = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "backup-validate-a", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    second = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "backup-validate-b", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    first_id = first.json()["data"]["id"]
    second_id = second.json()["data"]["id"]
    client.get(f"/api/v1/astron-claw/agent-tasks/{first.json()['data']['deployTaskId']}", headers=auth_headers)
    client.get(f"/api/v1/astron-claw/agent-tasks/{second.json()['data']['deployTaskId']}", headers=auth_headers)

    missing_backup_id = client.post(f"/api/v1/astron-claw/agents/{first_id}/backup-restore", headers=auth_headers, json={})
    assert missing_backup_id.status_code == 422

    backup = client.post(f"/api/v1/astron-claw/agents/{first_id}/backups", headers=auth_headers)
    backup_id = backup.json()["data"]["taskId"]

    cross_status = client.get(f"/api/v1/astron-claw/agents/{second_id}/backups/{backup_id}", headers=auth_headers)
    assert cross_status.status_code == 404

    cross_restore = client.post(
        f"/api/v1/astron-claw/agents/{second_id}/backup-restore",
        headers=auth_headers,
        json={"backupTaskId": backup_id},
    )
    assert cross_restore.status_code == 404

    restore = client.post(
        f"/api/v1/astron-claw/agents/{first_id}/backup-restore",
        headers=auth_headers,
        json={"backupTaskId": backup_id},
    )
    assert restore.status_code == 200


def test_batch_task_mock_worker_updates_counts(client, auth_headers):
    create = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "batch-agent", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    agent_id = create.json()["data"]["id"]
    client.get(f"/api/v1/astron-claw/agent-tasks/{create.json()['data']['deployTaskId']}", headers=auth_headers)

    batch = client.post(
        "/api/v1/astron-claw/batch-tasks",
        headers=auth_headers,
        json={"type": "stop", "scopeType": "selected", "targetIds": [agent_id], "strategy": {"batchSize": 10}},
    )
    assert batch.status_code == 200
    batch_id = batch.json()["data"]["id"]
    result = client.get(f"/api/v1/astron-claw/batch-tasks/{batch_id}", headers=auth_headers)
    assert result.status_code == 200
    assert result.json()["data"]["status"] == "success"
    assert result.json()["data"]["successCount"] == 1

    detail = client.get(f"/api/v1/astron-claw/agents/{agent_id}", headers=auth_headers)
    assert detail.json()["data"]["basic"]["status"] == "stopped"


def test_batch_items_and_export_validate_batch_id(client, auth_headers):
    missing_items = client.get("/api/v1/astron-claw/batch-tasks/bat_missing/items", headers=auth_headers)
    assert missing_items.status_code == 404
    assert missing_items.json()["data"]["field"] == "batchId"

    missing_export = client.get("/api/v1/astron-claw/batch-tasks/bat_missing/export", headers=auth_headers)
    assert missing_export.status_code == 404
    assert missing_export.json()["data"]["field"] == "batchId"

    first = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "batch-page-first", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    second = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "batch-page-second", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    first_id = first.json()["data"]["id"]
    second_id = second.json()["data"]["id"]

    batch = client.post(
        "/api/v1/astron-claw/batch-tasks",
        headers=auth_headers,
        json={"type": "stop", "scopeType": "selected", "targetIds": [first_id, second_id], "strategy": {"batchSize": 10}},
    )
    assert batch.status_code == 200
    batch_id = batch.json()["data"]["id"]

    page = client.get(f"/api/v1/astron-claw/batch-tasks/{batch_id}/items", headers=auth_headers, params={"page": 1, "pageSize": 1})
    assert page.status_code == 200
    data = page.json()["data"]
    assert data["page"] == 1
    assert data["pageSize"] == 1
    assert data["total"] == 2
    assert len(data["items"]) == 1


def test_batch_task_resume_skips_completed_items(client, auth_headers):
    first = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "batch-resume-first", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    second = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "batch-resume-second", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    first_id = first.json()["data"]["id"]
    second_id = second.json()["data"]["id"]
    client.get(f"/api/v1/astron-claw/agent-tasks/{first.json()['data']['deployTaskId']}", headers=auth_headers)
    client.get(f"/api/v1/astron-claw/agent-tasks/{second.json()['data']['deployTaskId']}", headers=auth_headers)

    batch = client.post(
        "/api/v1/astron-claw/batch-tasks",
        headers=auth_headers,
        json={"type": "stop", "scopeType": "selected", "targetIds": [first_id, second_id], "strategy": {"batchSize": 1}},
    )
    assert batch.status_code == 200
    batch_id = batch.json()["data"]["id"]

    first_poll = client.get(f"/api/v1/astron-claw/batch-tasks/{batch_id}", headers=auth_headers)
    assert first_poll.status_code == 200
    assert first_poll.json()["data"]["status"] == "running"
    assert first_poll.json()["data"]["successCount"] == 1

    first_detail = client.get(f"/api/v1/astron-claw/agents/{first_id}", headers=auth_headers)
    second_detail = client.get(f"/api/v1/astron-claw/agents/{second_id}", headers=auth_headers)
    assert first_detail.json()["data"]["basic"]["status"] == "stopped"
    assert second_detail.json()["data"]["basic"]["status"] == "running"

    second_poll = client.get(f"/api/v1/astron-claw/batch-tasks/{batch_id}", headers=auth_headers)
    assert second_poll.status_code == 200
    assert second_poll.json()["data"]["status"] == "success"
    assert second_poll.json()["data"]["successCount"] == 2

    items = client.get(f"/api/v1/astron-claw/batch-tasks/{batch_id}/items", headers=auth_headers)
    assert items.status_code == 200
    assert [item["status"] for item in items.json()["data"]["items"]] == ["success", "success"]

    first_after_resume = client.get(f"/api/v1/astron-claw/agents/{first_id}", headers=auth_headers)
    second_after_resume = client.get(f"/api/v1/astron-claw/agents/{second_id}", headers=auth_headers)
    assert first_after_resume.json()["data"]["basic"]["status"] == "stopped"
    assert second_after_resume.json()["data"]["basic"]["status"] == "stopped"


def test_runtime_sync_job_updates_metrics_and_records_failures(client, auth_headers):
    first = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "runtime-sync-ok", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    second = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "runtime-sync-fail", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    first_id = first.json()["data"]["id"]
    second_id = second.json()["data"]["id"]
    client.get(f"/api/v1/astron-claw/agent-tasks/{first.json()['data']['deployTaskId']}", headers=auth_headers)
    client.get(f"/api/v1/astron-claw/agent-tasks/{second.json()['data']['deployTaskId']}", headers=auth_headers)

    created = client.post(
        "/api/v1/astron-claw/sync-jobs",
        headers=auth_headers,
        json={
            "scopeType": "selected",
            "targetIds": [first_id, second_id],
            "metrics": {"containerCount": 3, "qps": 12.5, "latencyMs": 88, "currentUsers": 7, "maxUsers": 80},
            "failAgentIds": [second_id],
        },
    )
    assert created.status_code == 200
    data = created.json()["data"]
    assert data["status"] == "queued"
    assert data["total"] == 2

    detail = client.get(f"/api/v1/astron-claw/sync-jobs/{data['id']}", headers=auth_headers)
    assert detail.status_code == 200
    sync_data = detail.json()["data"]
    assert sync_data["status"] == "partial_success"
    assert sync_data["successCount"] == 1
    assert sync_data["failedCount"] == 1
    assert sync_data["progress"] == 100
    assert sync_data["errorMessage"] == "1 agent(s) sync failed"

    first_detail = client.get(f"/api/v1/astron-claw/agents/{first_id}", headers=auth_headers).json()["data"]["runtime"]
    assert first_detail["containerCount"] == 3
    assert first_detail["qps"] == 12.5
    assert first_detail["currentUsers"] == 7

    second_sync = client.post(f"/api/v1/astron-claw/agents/{second_id}/sync", headers=auth_headers, json={})
    assert second_sync.status_code == 200
    assert second_sync.json()["data"]["syncError"] is None

    listed = client.get("/api/v1/astron-claw/sync-jobs", headers=auth_headers, params={"status": "partial_success"})
    assert any(item["id"] == data["id"] for item in listed.json()["data"]["items"])

    audit_logs = client.get(
        "/api/v1/astron-claw/audit/operation-logs",
        headers=auth_headers,
        params={"module": "runtime_sync", "action": "partial_success"},
    )
    assert any(item["objectId"] == data["id"] for item in audit_logs.json()["data"]["items"])


def test_batch_task_respects_batch_size_across_polls(client, auth_headers):
    first = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "batch-size-first", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    second = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "batch-size-second", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    first_id = first.json()["data"]["id"]
    second_id = second.json()["data"]["id"]
    client.get(f"/api/v1/astron-claw/agent-tasks/{first.json()['data']['deployTaskId']}", headers=auth_headers)
    client.get(f"/api/v1/astron-claw/agent-tasks/{second.json()['data']['deployTaskId']}", headers=auth_headers)

    batch = client.post(
        "/api/v1/astron-claw/batch-tasks",
        headers=auth_headers,
        json={"type": "stop", "scopeType": "selected", "targetIds": [first_id, second_id], "strategy": {"batchSize": 1}},
    )
    assert batch.status_code == 200
    batch_id = batch.json()["data"]["id"]

    first_poll = client.get(f"/api/v1/astron-claw/batch-tasks/{batch_id}", headers=auth_headers)
    assert first_poll.status_code == 200
    assert first_poll.json()["data"]["status"] == "running"
    assert first_poll.json()["data"]["successCount"] == 1
    assert first_poll.json()["data"]["progress"] == 50

    second_poll = client.get(f"/api/v1/astron-claw/batch-tasks/{batch_id}", headers=auth_headers)
    assert second_poll.status_code == 200
    assert second_poll.json()["data"]["status"] == "success"
    assert second_poll.json()["data"]["successCount"] == 2
    assert second_poll.json()["data"]["operator"]["name"] == "系统管理员"
    assert second_poll.json()["data"]["strategy"]["batchSize"] == 1


def test_batch_task_pause_on_failure_leaves_remaining_items_queued(client, auth_headers):
    first = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "batch-pause-first", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    second = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "batch-pause-second", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    first_id = first.json()["data"]["id"]
    second_id = second.json()["data"]["id"]
    client.get(f"/api/v1/astron-claw/agent-tasks/{first.json()['data']['deployTaskId']}", headers=auth_headers)
    client.get(f"/api/v1/astron-claw/agent-tasks/{second.json()['data']['deployTaskId']}", headers=auth_headers)

    batch = client.post(
        "/api/v1/astron-claw/batch-tasks",
        headers=auth_headers,
        json={"type": "stop", "scopeType": "selected", "targetIds": [first_id, second_id], "strategy": {"batchSize": 10, "pauseOnFailure": True}},
    )
    assert batch.status_code == 200
    batch_id = batch.json()["data"]["id"]

    from app.db import SessionLocal
    from app.models import BatchTaskItem
    from sqlalchemy import select

    with SessionLocal() as db:
        first_item = db.execute(select(BatchTaskItem).where(BatchTaskItem.batch_task_id == batch_id)).scalars().first()
        first_item.target_id = "agt_db_missing"
        db.commit()

    result = client.get(f"/api/v1/astron-claw/batch-tasks/{batch_id}", headers=auth_headers)
    assert result.status_code == 200
    assert result.json()["data"]["status"] == "paused"
    assert result.json()["data"]["failedCount"] == 1
    assert result.json()["data"]["successCount"] == 0
    assert result.json()["data"]["progress"] == 50

    items = client.get(f"/api/v1/astron-claw/batch-tasks/{batch_id}/items", headers=auth_headers)
    statuses = {item["status"] for item in items.json()["data"]["items"]}
    assert statuses == {"failed", "queued"}
    failed_item = next(item for item in items.json()["data"]["items"] if item["status"] == "failed")
    assert failed_item["errorCode"] == "AGENT_NOT_FOUND"
    assert failed_item["startedAt"]
    assert failed_item["endedAt"]


def test_high_risk_batch_requires_approval(client, auth_headers):
    create = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "delete-approval-agent", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    agent_id = create.json()["data"]["id"]
    client.get(f"/api/v1/astron-claw/agent-tasks/{create.json()['data']['deployTaskId']}", headers=auth_headers)
    client.post(f"/api/v1/astron-claw/agents/{agent_id}/stop", headers=auth_headers, json={})

    batch = client.post(
        "/api/v1/astron-claw/batch-tasks",
        headers=auth_headers,
        json={"type": "delete", "scopeType": "selected", "targetIds": [agent_id], "reason": "cleanup"},
    )
    assert batch.status_code == 200
    data = batch.json()["data"]
    assert data["status"] == "pending_approval"
    assert data["approvalId"]

    pending = client.get(f"/api/v1/astron-claw/batch-tasks/{data['id']}", headers=auth_headers)
    assert pending.json()["data"]["status"] == "pending_approval"
    approval_detail = client.get(f"/api/v1/astron-claw/approvals/{data['approvalId']}", headers=auth_headers)
    assert approval_detail.status_code == 200
    assert approval_detail.json()["data"]["steps"][0]["stepNo"] == 1
    assert approval_detail.json()["data"]["steps"][0]["decision"] is None

    approved = client.post(f"/api/v1/astron-claw/approvals/{data['approvalId']}/approve", headers=auth_headers, json={"comment": "approved for cleanup"})
    assert approved.status_code == 200
    approval_step = approved.json()["data"]["steps"][0]
    assert approval_step["decision"] == "approved"
    assert approval_step["approverId"] == "u001"
    assert approval_step["comment"] == "approved for cleanup"
    assert approval_step["decidedAt"]
    ready = client.get(f"/api/v1/astron-claw/batch-tasks/{data['id']}", headers=auth_headers)
    assert ready.json()["data"]["status"] in {"success", "partial_success"}


def test_high_risk_batch_uses_frozen_approval_snapshot(client, auth_headers):
    first = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "frozen-approval-first", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    second = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "frozen-approval-second", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    first_id = first.json()["data"]["id"]
    second_id = second.json()["data"]["id"]
    client.get(f"/api/v1/astron-claw/agent-tasks/{first.json()['data']['deployTaskId']}", headers=auth_headers)
    client.get(f"/api/v1/astron-claw/agent-tasks/{second.json()['data']['deployTaskId']}", headers=auth_headers)
    client.post(f"/api/v1/astron-claw/agents/{first_id}/stop", headers=auth_headers, json={})
    client.post(f"/api/v1/astron-claw/agents/{second_id}/stop", headers=auth_headers, json={})

    batch = client.post(
        "/api/v1/astron-claw/batch-tasks",
        headers=auth_headers,
        json={"type": "delete", "scopeType": "selected", "targetIds": [first_id], "reason": "frozen cleanup"},
    )
    assert batch.status_code == 200
    batch_data = batch.json()["data"]

    from app.db import SessionLocal
    from app.models import BatchTask, BatchTaskItem
    from sqlalchemy import select

    with SessionLocal() as db:
        stored = db.get(BatchTask, batch_data["id"])
        stored.scope_snapshot = {"targetIds": [second_id], "tampered": True}
        item = db.execute(select(BatchTaskItem).where(BatchTaskItem.batch_task_id == stored.id)).scalars().first()
        item.target_id = second_id
        db.commit()

    approved = client.post(f"/api/v1/astron-claw/approvals/{batch_data['approvalId']}/approve", headers=auth_headers, json={})
    assert approved.status_code == 200
    result = client.get(f"/api/v1/astron-claw/batch-tasks/{batch_data['id']}", headers=auth_headers)
    assert result.json()["data"]["status"] == "success"

    first_detail = client.get(f"/api/v1/astron-claw/agents/{first_id}", headers=auth_headers)
    second_detail = client.get(f"/api/v1/astron-claw/agents/{second_id}", headers=auth_headers)
    assert first_detail.status_code == 404
    assert second_detail.status_code == 200


def test_high_risk_batch_cannot_bypass_with_pending_approval_id(client, auth_headers):
    create = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "pending-bypass-agent", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    agent_id = create.json()["data"]["id"]
    client.get(f"/api/v1/astron-claw/agent-tasks/{create.json()['data']['deployTaskId']}", headers=auth_headers)
    client.post(f"/api/v1/astron-claw/agents/{agent_id}/stop", headers=auth_headers, json={})

    pending = client.post(
        "/api/v1/astron-claw/batch-tasks",
        headers=auth_headers,
        json={"type": "delete", "scopeType": "selected", "targetIds": [agent_id], "reason": "needs approval"},
    )
    approval_id = pending.json()["data"]["approvalId"]

    bypass = client.post(
        "/api/v1/astron-claw/batch-tasks",
        headers=auth_headers,
        json={"type": "delete", "scopeType": "selected", "targetIds": [agent_id], "approvalId": approval_id},
    )
    assert bypass.status_code == 409
    assert bypass.json()["code"] == 409002
    assert bypass.json()["data"]["status"] == "pending"


def test_high_risk_batch_with_approved_id_uses_approval_snapshot(client, auth_headers):
    first = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "approved-snapshot-first", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    second = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "approved-snapshot-second", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    first_id = first.json()["data"]["id"]
    second_id = second.json()["data"]["id"]
    client.get(f"/api/v1/astron-claw/agent-tasks/{first.json()['data']['deployTaskId']}", headers=auth_headers)
    client.get(f"/api/v1/astron-claw/agent-tasks/{second.json()['data']['deployTaskId']}", headers=auth_headers)
    client.post(f"/api/v1/astron-claw/agents/{first_id}/stop", headers=auth_headers, json={})
    client.post(f"/api/v1/astron-claw/agents/{second_id}/stop", headers=auth_headers, json={})

    approval = client.post(
        "/api/v1/astron-claw/approvals",
        headers=auth_headers,
        json={
            "type": "batch_delete_agent",
            "riskLevel": "high",
            "reason": "delete approved target",
            "payload": {"targetIds": [first_id], "batchType": "delete"},
        },
    )
    approval_id = approval.json()["data"]["id"]
    client.post(f"/api/v1/astron-claw/approvals/{approval_id}/approve", headers=auth_headers, json={})

    batch = client.post(
        "/api/v1/astron-claw/batch-tasks",
        headers=auth_headers,
        json={"type": "delete", "scopeType": "selected", "targetIds": [second_id], "approvalId": approval_id},
    )
    assert batch.status_code == 200
    assert batch.json()["data"]["total"] == 1

    result = client.get(f"/api/v1/astron-claw/batch-tasks/{batch.json()['data']['id']}", headers=auth_headers)
    assert result.json()["data"]["status"] == "success"

    first_detail = client.get(f"/api/v1/astron-claw/agents/{first_id}", headers=auth_headers)
    second_detail = client.get(f"/api/v1/astron-claw/agents/{second_id}", headers=auth_headers)
    assert first_detail.status_code == 404
    assert second_detail.status_code == 200


def test_dev_file_path_whitelist(client, auth_headers):
    create = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "dev-file-whitelist", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    agent_id = create.json()["data"]["id"]

    ok = client.get(
        f"/api/v1/astron-claw/agents/{agent_id}/dev-file/meta",
        headers=auth_headers,
        params={"path": "/root/.openclaw/demo.md"},
    )
    assert ok.status_code == 200

    bad = client.get(
        f"/api/v1/astron-claw/agents/{agent_id}/dev-file/meta",
        headers=auth_headers,
        params={"path": "/etc/passwd"},
    )
    assert bad.status_code == 422
    assert bad.json()["code"] == 400001

    sibling = client.get(
        f"/api/v1/astron-claw/agents/{agent_id}/dev-file/meta",
        headers=auth_headers,
        params={"path": "/root/.openclaw2/demo.md"},
    )
    assert sibling.status_code == 422
    assert sibling.json()["code"] == 400001


def test_agent_proxy_helpers_reject_missing_agent(client, auth_headers):
    assert client.get("/api/v1/astron-claw/agents/missing/runtime-skills", headers=auth_headers).status_code == 404
    assert client.get("/api/v1/astron-claw/agents/missing/skill-env-vars", headers=auth_headers).status_code == 404
    assert client.request("DELETE", "/api/v1/astron-claw/agents/missing/skill-env-vars", headers=auth_headers, json={}).status_code == 404
    assert client.get("/api/v1/astron-claw/agents/missing/dev-file/meta", headers=auth_headers, params={"path": "/root/.openclaw/demo.md"}).status_code == 404
    assert client.put("/api/v1/astron-claw/agents/missing/dev-file/content", headers=auth_headers, json={"path": "/root/.openclaw/demo.md", "content": ""}).status_code == 404
    assert client.get("/api/v1/astron-claw/agents/missing/memory-preview", headers=auth_headers).status_code == 404
    assert client.get("/api/v1/astron-claw/agents/missing/plugins/astronmem", headers=auth_headers).status_code == 404
    assert client.post("/api/v1/astron-claw/agents/missing/plugins/astronmem", headers=auth_headers, json={"action": "enable"}).status_code == 404


def test_dev_file_save_records_audit_and_checks_etag(client, auth_headers):
    create = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "dev-file-agent", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    agent_id = create.json()["data"]["id"]
    path = "/root/.openclaw/demo.md"

    saved = client.put(
        f"/api/v1/astron-claw/agents/{agent_id}/dev-file/content",
        headers=auth_headers,
        json={"path": path, "content": "# updated\n"},
    )
    assert saved.status_code == 200
    etag = saved.json()["data"]["etag"]
    assert saved.json()["data"]["auditId"].startswith("dfa_")

    meta = client.get(
        f"/api/v1/astron-claw/agents/{agent_id}/dev-file/meta",
        headers=auth_headers,
        params={"path": path},
    )
    assert meta.status_code == 200
    assert meta.json()["data"]["etag"] == etag

    files = client.get(
        f"/api/v1/astron-claw/agents/{agent_id}/dev-files",
        headers=auth_headers,
        params={"path": "/root/.openclaw"},
    )
    assert any(item["path"] == path and item["etag"] == etag for item in files.json()["data"]["items"])

    search = client.get(
        f"/api/v1/astron-claw/agents/{agent_id}/dev-files/search",
        headers=auth_headers,
        params={"path": "/root/.openclaw", "keyword": "demo"},
    )
    assert any(item["path"] == path for item in search.json()["data"]["items"])

    conflict = client.put(
        f"/api/v1/astron-claw/agents/{agent_id}/dev-file/content",
        headers=auth_headers,
        json={"path": path, "content": "# stale\n", "etag": "stale-etag"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == 409001
    assert conflict.json()["data"]["currentEtag"] == etag

    audit_logs = client.get(
        "/api/v1/astron-claw/audit/operation-logs",
        headers=auth_headers,
        params={"module": "dev_file", "action": "save"},
    )
    assert any(item["objectId"] == path for item in audit_logs.json()["data"]["items"])


def test_astronmem_plugin_toggle_persists_and_audits(client, auth_headers):
    create = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "astronmem-agent", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    agent_id = create.json()["data"]["id"]

    default = client.get(f"/api/v1/astron-claw/agents/{agent_id}/plugins/astronmem", headers=auth_headers)
    assert default.status_code == 200
    assert default.json()["data"]["status"] == "disabled"

    enabled = client.post(
        f"/api/v1/astron-claw/agents/{agent_id}/plugins/astronmem",
        headers=auth_headers,
        json={"action": "enable"},
    )
    assert enabled.status_code == 200
    assert enabled.json()["data"]["status"] == "enabled"

    status = client.get(f"/api/v1/astron-claw/agents/{agent_id}/plugins/astronmem", headers=auth_headers)
    assert status.json()["data"]["status"] == "enabled"

    preview = client.get(f"/api/v1/astron-claw/agents/{agent_id}/memory-preview", headers=auth_headers)
    assert preview.status_code == 200
    assert preview.json()["data"]["pluginStatus"] == "enabled"
    assert "apiKey" not in str(preview.json()["data"])

    disabled = client.post(
        f"/api/v1/astron-claw/agents/{agent_id}/plugins/astronmem",
        headers=auth_headers,
        json={"action": "disable"},
    )
    assert disabled.status_code == 200
    assert disabled.json()["data"]["status"] == "disabled"

    audit_logs = client.get(
        "/api/v1/astron-claw/audit/operation-logs",
        headers=auth_headers,
        params={"module": "memory", "action": "astronmem_toggle"},
    )
    assert any(item["objectId"] == agent_id for item in audit_logs.json()["data"]["items"])


def test_policy_channel_and_diagnosis_crud(client, auth_headers):
    quota = client.post(
        "/api/v1/astron-claw/model-quotas",
        headers=auth_headers,
        json={"scopeType": "department", "scopeId": "dep002", "modelId": "m001", "qpsLimit": 10},
    )
    assert quota.status_code == 200
    quota_id = quota.json()["data"]["id"]
    assert client.put(f"/api/v1/astron-claw/model-quotas/{quota_id}", headers=auth_headers, json={"dailyCallLimit": 1000}).status_code == 200

    channel = client.post(
        "/api/v1/astron-claw/channels",
        headers=auth_headers,
        json={"name": "企业微信", "type": "wecom", "callbackUrl": "https://example.com/callback"},
    )
    assert channel.status_code == 200
    channel_id = channel.json()["data"]["id"]
    assert client.put(f"/api/v1/astron-claw/channels/{channel_id}", headers=auth_headers, json={"status": "disabled"}).status_code == 200
    reconnect = client.post(f"/api/v1/astron-claw/channels/{channel_id}/reconnect", headers=auth_headers)
    assert reconnect.status_code == 200
    assert reconnect.json()["data"]["status"] == "enabled"
    disabled = client.post(f"/api/v1/astron-claw/channels/{channel_id}/disable", headers=auth_headers)
    assert disabled.status_code == 200
    assert disabled.json()["data"]["status"] == "disabled"

    agent = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "business-system-agent", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    system = client.post(
        "/api/v1/astron-claw/business-systems",
        headers=auth_headers,
        json={"name": "CRM", "embedType": "iframe", "ssoMode": "backend"},
    )
    assert system.status_code == 200
    system_id = system.json()["data"]["id"]
    bind_system = client.put(
        f"/api/v1/astron-claw/business-systems/{system_id}/agents",
        headers=auth_headers,
        json={"agentIds": [agent.json()["data"]["id"]]},
    )
    assert bind_system.status_code == 200
    assert bind_system.json()["data"]["allowedAgentIds"] == [agent.json()["data"]["id"]]

    channel_audit = client.get("/api/v1/astron-claw/channel-audit-logs", headers=auth_headers)
    audit_items = channel_audit.json()["data"]["items"]
    assert any(item["module"] == "channel" and item["objectId"] == channel_id for item in audit_items)
    assert any(item["module"] == "business_system" and item["objectId"] == system_id for item in audit_items)

    bind_channel = client.put(
        f"/api/v1/astron-claw/channels/{channel_id}/agents",
        headers=auth_headers,
        json={"agentIds": [agent.json()["data"]["id"]]},
    )
    assert bind_channel.status_code == 200
    assert bind_channel.json()["data"]["agentIds"] == [agent.json()["data"]["id"]]

    channel_binds = client.get(f"/api/v1/astron-claw/channels/{channel_id}/agents", headers=auth_headers)
    assert channel_binds.status_code == 200
    assert channel_binds.json()["data"]["items"][0]["agentId"] == agent.json()["data"]["id"]

    enabled = client.put(f"/api/v1/astron-claw/channels/{channel_id}", headers=auth_headers, json={"status": "enabled"})
    assert enabled.status_code == 200
    message = client.post(
        f"/api/v1/astron-claw/channels/{channel_id}/messages",
        headers=auth_headers,
        json={"sourceType": "alert", "sourceId": "alt_channel", "agentId": agent.json()["data"]["id"], "messageType": "alert_push"},
    )
    assert message.status_code == 200
    assert message.json()["data"]["status"] == "success"
    message_logs = client.get("/api/v1/astron-claw/channel-message-logs", headers=auth_headers, params={"channelId": channel_id})
    assert any(item["sourceId"] == "alt_channel" for item in message_logs.json()["data"]["items"])

    system_grants = client.get(f"/api/v1/astron-claw/business-systems/{system_id}/agents", headers=auth_headers)
    assert system_grants.status_code == 200
    assert system_grants.json()["data"]["items"][0]["agentId"] == agent.json()["data"]["id"]

    access = client.post(
        f"/api/v1/astron-claw/business-systems/{system_id}/access",
        headers=auth_headers,
        json={"agentId": agent.json()["data"]["id"], "source": "contract-portal", "action": "embed_access"},
    )
    assert access.status_code == 200
    assert access.json()["data"]["allowed"] is True
    system_audit = client.get("/api/v1/astron-claw/business-system-audit-logs", headers=auth_headers, params={"systemId": system_id})
    assert any(item["source"] == "contract-portal" and item["result"] == "success" for item in system_audit.json()["data"]["items"])

    kb = client.post(
        "/api/v1/astron-claw/diagnosis-kb",
        headers=auth_headers,
        json={
            "module": "agent",
            "errorCode": "AGENT_SESSION_EXPIRED",
            "symptom": "实例异常",
            "reason": "会话失效",
            "solution": "重新部署",
            "verificationMethod": "重新部署后确认实例状态为 running",
        },
    )
    assert kb.status_code == 200
    entry_id = kb.json()["data"]["id"]
    assert kb.json()["data"]["verificationMethod"] == "重新部署后确认实例状态为 running"
    listed = client.get("/api/v1/astron-claw/diagnosis-kb", headers=auth_headers, params={"module": "agent", "errorCode": "AGENT_SESSION_EXPIRED"})
    assert listed.status_code == 200
    assert listed.json()["data"]["items"][0]["verificationMethod"] == "重新部署后确认实例状态为 running"
    keyword_hit = client.get("/api/v1/astron-claw/diagnosis-kb", headers=auth_headers, params={"keyword": "running"})
    assert any(item["id"] == entry_id for item in keyword_hit.json()["data"]["items"])
    keyword_miss = client.get("/api/v1/astron-claw/diagnosis-kb", headers=auth_headers, params={"module": "agent", "keyword": "不存在的诊断关键字"})
    assert keyword_miss.json()["data"]["items"] == []
    updated_kb = client.put(
        f"/api/v1/astron-claw/diagnosis-kb/{entry_id}",
        headers=auth_headers,
        json={"tags": ["agent"], "verificationMethod": "确认告警关闭且最近一次探针成功"},
    )
    assert updated_kb.status_code == 200
    assert updated_kb.json()["data"]["verificationMethod"] == "确认告警关闭且最近一次探针成功"
    assert client.delete(f"/api/v1/astron-claw/diagnosis-kb/{entry_id}", headers=auth_headers).status_code == 200

    seeded = client.get("/api/v1/astron-claw/diagnosis-kb", headers=auth_headers, params={"module": "claw_proxy", "errorCode": "400003"})
    assert seeded.status_code == 200
    seeded_item = seeded.json()["data"]["items"][0]
    assert seeded_item["symptom"] == "沙箱会话失效"
    assert seeded_item["reason"]
    assert seeded_item["solution"]
    assert seeded_item["verificationMethod"]

    tree = client.post(
        "/api/v1/astron-claw/diagnosis-decision-trees",
        headers=auth_headers,
        json={
            "name": "模型网关诊断树",
            "module": "model_gateway",
            "entryNodeId": "n1",
            "nodes": [
                {"id": "n1", "type": "question", "title": "探针是否失败"},
                {"id": "n2", "type": "solution", "title": "切换备用模型"},
            ],
            "edges": [{"from": "n1", "to": "n2", "condition": "yes"}],
        },
    )
    assert tree.status_code == 200
    tree_data = tree.json()["data"]
    assert tree_data["id"].startswith("dtree_")
    assert tree_data["version"] == 1
    assert tree_data["nodes"][0]["id"] == "n1"

    listed_trees = client.get(
        "/api/v1/astron-claw/diagnosis-decision-trees",
        headers=auth_headers,
        params={"module": "model_gateway"},
    )
    assert listed_trees.status_code == 200
    assert any(item["id"] == tree_data["id"] for item in listed_trees.json()["data"]["items"])

    updated_tree = client.put(
        f"/api/v1/astron-claw/diagnosis-decision-trees/{tree_data['id']}",
        headers=auth_headers,
        json={"status": "disabled", "nodes": tree_data["nodes"] + [{"id": "n3", "type": "check", "title": "查看路由策略"}]},
    )
    assert updated_tree.status_code == 200
    assert updated_tree.json()["data"]["version"] == 2
    assert updated_tree.json()["data"]["status"] == "disabled"

    diagnosis_audit = client.get(
        "/api/v1/astron-claw/audit/operation-logs",
        headers=auth_headers,
        params={"module": "diagnosis"},
    )
    actions = {item["action"] for item in diagnosis_audit.json()["data"]["items"]}
    assert {"create_decision_tree", "update_decision_tree"} <= actions


def test_channel_rate_limits_write_failed_message_log_and_audit(client, auth_headers):
    channel = client.post(
        "/api/v1/astron-claw/channels",
        headers=auth_headers,
        json={
            "name": "限流渠道",
            "type": "wecom",
            "callbackUrl": "https://example.com/rate-limit",
            "userRateLimitPerMinute": 1,
            "qpsLimit": 5,
            "dailyMessageLimit": 10,
        },
    )
    assert channel.status_code == 200
    channel_data = channel.json()["data"]
    channel_id = channel_data["id"]
    assert channel_data["userRateLimitPerMinute"] == 1
    assert channel_data["qpsLimit"] == 5
    assert channel_data["dailyMessageLimit"] == 10

    first = client.post(
        f"/api/v1/astron-claw/channels/{channel_id}/messages",
        headers=auth_headers,
        json={"sourceType": "alert", "sourceId": "alt_rate_1", "messageType": "alert_push"},
    )
    assert first.status_code == 200
    assert first.json()["data"]["status"] == "success"

    limited = client.post(
        f"/api/v1/astron-claw/channels/{channel_id}/messages",
        headers=auth_headers,
        json={"sourceType": "alert", "sourceId": "alt_rate_2", "messageType": "alert_push"},
    )
    assert limited.status_code == 422
    limited_data = limited.json()["data"]
    assert limited_data["reason"] == "user_rate_limit"
    assert limited_data["channelId"] == channel_id
    assert limited_data["messageLogId"].startswith("cml_")

    logs = client.get("/api/v1/astron-claw/channel-message-logs", headers=auth_headers, params={"channelId": channel_id})
    assert logs.status_code == 200
    failed_log = next(item for item in logs.json()["data"]["items"] if item["sourceId"] == "alt_rate_2")
    assert failed_log["status"] == "failed"
    assert failed_log["result"]["reason"] == "user_rate_limit"

    audits = client.get("/api/v1/astron-claw/channel-audit-logs", headers=auth_headers, params={"action": "send_message"})
    assert any(item["objectId"] == limited_data["messageLogId"] and item["result"] == "failed" for item in audits.json()["data"]["items"])


def test_channel_message_requires_active_agent_binding(client, auth_headers):
    agent = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "channel-bound-agent", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    agent_id = agent.json()["data"]["id"]
    channel = client.post(
        "/api/v1/astron-claw/channels",
        headers=auth_headers,
        json={"name": "绑定校验渠道", "type": "webhook", "callbackUrl": "https://example.com/bind-check"},
    )
    channel_id = channel.json()["data"]["id"]

    denied = client.post(
        f"/api/v1/astron-claw/channels/{channel_id}/messages",
        headers=auth_headers,
        json={"sourceType": "alert", "sourceId": "alt_unbound", "agentId": agent_id, "messageType": "alert_push"},
    )
    assert denied.status_code == 403
    denied_data = denied.json()["data"]
    assert denied_data["reason"] == "agent_not_bound"
    assert denied_data["messageLogId"].startswith("cml_")

    logs = client.get("/api/v1/astron-claw/channel-message-logs", headers=auth_headers, params={"channelId": channel_id})
    failed_log = next(item for item in logs.json()["data"]["items"] if item["id"] == denied_data["messageLogId"])
    assert failed_log["status"] == "failed"
    assert failed_log["result"]["reason"] == "agent_not_bound"

    audits = client.get("/api/v1/astron-claw/channel-audit-logs", headers=auth_headers, params={"action": "send_message"})
    assert any(item["objectId"] == denied_data["messageLogId"] and item["result"] == "failed" for item in audits.json()["data"]["items"])

    bind = client.put(
        f"/api/v1/astron-claw/channels/{channel_id}/agents",
        headers=auth_headers,
        json={"agentIds": [agent_id]},
    )
    assert bind.status_code == 200

    allowed = client.post(
        f"/api/v1/astron-claw/channels/{channel_id}/messages",
        headers=auth_headers,
        json={"sourceType": "alert", "sourceId": "alt_bound", "agentId": agent_id, "messageType": "alert_push"},
    )
    assert allowed.status_code == 200
    assert allowed.json()["data"]["status"] == "success"


def test_openapi_generates(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/api/v1/astron-claw/agents" in response.json()["paths"]


def test_frontend_delivery_doc_operations_exist_in_openapi(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    implemented = {
        (
            method.upper(),
            re.sub(r"\{[^}]+\}", "{}", path.replace("/api/v1/astron-claw", "")),
        )
        for path, path_item in spec["paths"].items()
        for method in path_item
        if method.lower() in {"get", "post", "put", "patch", "delete"}
    }
    docs_path = Path(__file__).resolve().parents[3] / "backend-delivery-docs" / "04-frontend-api-documentation.md"
    text = docs_path.read_text(encoding="utf-8")
    documented = set()
    for match in re.finditer(r"\b(GET|POST|PUT|DELETE|PATCH)\s+(/[^\s`]+)", text):
        method = match.group(1)
        path = match.group(2).split("?", 1)[0]
        if path.startswith(("/api/v1/bot", "/deploy", "/skill", "/backup")):
            continue
        if path.startswith("/api/v1/astron-claw"):
            path = path.replace("/api/v1/astron-claw", "") or "/"
        if path.startswith("/api/"):
            continue
        documented.add((method, re.sub(r"\{[^}]+\}", "{}", path)))

    missing = documented - implemented
    assert len(documented) >= 150
    assert not missing


def test_audit_export_requires_approval_and_uses_frozen_query(client, auth_headers):
    export = client.get("/api/v1/astron-claw/audit/export", headers=auth_headers, params={"module": "agent"})
    assert export.status_code == 200
    data = export.json()["data"]
    assert data["status"] == "pending_approval"
    assert data["approvalId"].startswith("apr_")
    assert data["payload"]["query"] == {"module": "agent"}

    blocked = client.get("/api/v1/astron-claw/audit/export", headers=auth_headers, params={"approvalId": data["approvalId"]})
    assert blocked.status_code == 409
    assert blocked.json()["code"] == 409002

    from app.db import SessionLocal
    from app.models import ApprovalRequest

    with SessionLocal() as db:
        approval = db.get(ApprovalRequest, data["approvalId"])
        snapshot = dict(approval.payload_snapshot)
        snapshot["query"] = {"module": "model"}
        approval.payload_snapshot = snapshot
        db.commit()

    approved = client.post(f"/api/v1/astron-claw/approvals/{data['approvalId']}/approve", headers=auth_headers, json={})
    assert approved.status_code == 200

    approved_export = client.get(
        "/api/v1/astron-claw/audit/export",
        headers=auth_headers,
        params={"approvalId": data["approvalId"], "module": "agent"},
    )
    assert approved_export.status_code == 200
    task = approved_export.json()["data"]
    assert task["taskId"].startswith("exp_")
    assert task["downloadUrl"].startswith("/api/v1/astron-claw/exports/audit-")
    assert task["watermark"]
    assert task["approvalId"] == data["approvalId"]
    assert task["query"] == {"module": "model"}

    exports = client.get("/api/v1/astron-claw/exports", headers=auth_headers, params={"type": "audit"})
    assert exports.status_code == 200
    assert any(item["taskId"] == task["taskId"] for item in exports.json()["data"]["items"])

    export_detail = client.get(f"/api/v1/astron-claw/exports/{task['taskId']}", headers=auth_headers)
    assert export_detail.status_code == 200
    assert export_detail.json()["data"]["downloadUrl"] == task["downloadUrl"]

    file_name = task["downloadUrl"].rsplit("/", 1)[-1]
    export_by_file = client.get(f"/api/v1/astron-claw/exports/{file_name}", headers=auth_headers)
    assert export_by_file.status_code == 200
    assert export_by_file.json()["data"]["taskId"] == task["taskId"]

    download = client.get(f"/api/v1/astron-claw/exports/{task['taskId']}/download", headers=auth_headers)
    assert download.status_code == 200
    assert download.json()["data"]["fileName"] == file_name
    assert download.json()["data"]["watermark"] == task["watermark"]
    sensitive_download = client.get(
        "/api/v1/astron-claw/audit/sensitive-events",
        headers=auth_headers,
        params={"eventType": "data_export_download", "objectId": task["taskId"]},
    )
    assert sensitive_download.status_code == 200
    assert sensitive_download.json()["data"]["items"][0]["detail"]["exportType"] == "audit"

    logs = client.get("/api/v1/astron-claw/audit/operation-logs", headers=auth_headers)
    assert logs.status_code == 200
    assert any(item["module"] == "export" and item["action"] == "audit" for item in logs.json()["data"]["items"])
    assert any(item["module"] == "export" and item["action"] == "request_approval" for item in logs.json()["data"]["items"])
    assert any(item["module"] == "export" and item["action"] == "download" and item["objectId"] == task["taskId"] for item in logs.json()["data"]["items"])


def test_model_call_logs_export_requires_approval_and_uses_frozen_query(client, auth_headers):
    export = client.get(
        "/api/v1/astron-claw/audit/model-call-logs/export",
        headers=auth_headers,
        params={"modelId": "m001", "status": "success"},
    )
    assert export.status_code == 200
    data = export.json()["data"]
    assert data["status"] == "pending_approval"
    assert data["payload"]["exportType"] == "model_call_logs"
    assert data["payload"]["query"] == {"modelId": "m001", "status": "success"}

    blocked = client.get(
        "/api/v1/astron-claw/audit/model-call-logs/export",
        headers=auth_headers,
        params={"approvalId": data["approvalId"]},
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == 409002

    from app.db import SessionLocal
    from app.models import ApprovalRequest

    with SessionLocal() as db:
        approval = db.get(ApprovalRequest, data["approvalId"])
        snapshot = dict(approval.payload_snapshot)
        snapshot["query"] = {"modelId": "m002", "status": "failed"}
        approval.payload_snapshot = snapshot
        db.commit()

    approved = client.post(f"/api/v1/astron-claw/approvals/{data['approvalId']}/approve", headers=auth_headers, json={})
    assert approved.status_code == 200

    approved_export = client.get(
        "/api/v1/astron-claw/audit/model-call-logs/export",
        headers=auth_headers,
        params={"approvalId": data["approvalId"], "modelId": "m001"},
    )
    assert approved_export.status_code == 200
    task = approved_export.json()["data"]
    assert task["taskId"].startswith("exp_")
    assert task["downloadUrl"].startswith("/api/v1/astron-claw/exports/model_call_logs-")
    assert task["watermark"]
    assert task["approvalId"] == data["approvalId"]
    assert task["query"] == {"modelId": "m002", "status": "failed"}

    logs = client.get("/api/v1/astron-claw/audit/operation-logs", headers=auth_headers, params={"module": "export"})
    assert logs.status_code == 200
    assert any(item["action"] == "model_call_logs" for item in logs.json()["data"]["items"])


def test_audit_log_integrity_marks_tampered_records(client, auth_headers):
    requested = client.get(
        "/api/v1/astron-claw/audit/export",
        headers=auth_headers,
        params={"module": "agent"},
    )
    assert requested.status_code == 200

    logs = client.get(
        "/api/v1/astron-claw/audit/operation-logs",
        headers=auth_headers,
        params={"module": "export", "action": "request_approval"},
    )
    assert logs.status_code == 200
    item = logs.json()["data"]["items"][0]
    assert item["integrityStatus"] == "valid"

    from app.db import SessionLocal
    from app.models import AuditLog

    with SessionLocal() as db:
        row = db.get(AuditLog, item["id"])
        row.after_value = dict(row.after_value or {}) | {"tampered": True}
        db.commit()

    tampered = client.get(
        "/api/v1/astron-claw/audit/operation-logs",
        headers=auth_headers,
        params={"module": "export", "action": "request_approval"},
    )
    assert tampered.status_code == 200
    assert tampered.json()["data"]["items"][0]["integrityStatus"] == "tampered"


def test_security_policy_disable_requires_approval_and_uses_snapshot(client, auth_headers):
    policies = client.get("/api/v1/astron-claw/security-policies", headers=auth_headers, params={"category": "export"})
    assert policies.status_code == 200
    policy = next(item for item in policies.json()["data"] if item["id"] == "sec_pol_002")
    assert policy["status"] == "enabled"

    requested = client.put(
        "/api/v1/astron-claw/security-policies/sec_pol_002",
        headers=auth_headers,
        json={"status": "disabled", "reason": "temporary disable"},
    )
    assert requested.status_code == 200
    data = requested.json()["data"]
    assert data["status"] == "pending_approval"
    assert data["payload"]["status"] == "disabled"
    approval_id = data["approvalId"]

    still_enabled = client.get("/api/v1/astron-claw/security-policies/sec_pol_002", headers=auth_headers)
    assert still_enabled.json()["data"]["status"] == "enabled"

    from app.db import SessionLocal
    from app.models import ApprovalRequest

    with SessionLocal() as db:
        approval = db.get(ApprovalRequest, approval_id)
        snapshot = dict(approval.payload_snapshot)
        snapshot["config"] = {"approvalRequired": False, "watermarkRequired": False}
        approval.payload_snapshot = snapshot
        db.commit()

    approved = client.post(f"/api/v1/astron-claw/approvals/{approval_id}/approve", headers=auth_headers, json={})
    assert approved.status_code == 200

    changed = client.get("/api/v1/astron-claw/security-policies/sec_pol_002", headers=auth_headers)
    assert changed.status_code == 200
    changed_data = changed.json()["data"]
    assert changed_data["status"] == "disabled"
    assert changed_data["config"] == {"approvalRequired": False, "watermarkRequired": False}

    audit_logs = client.get(
        "/api/v1/astron-claw/audit/operation-logs",
        headers=auth_headers,
        params={"module": "security", "action": "policy_change"},
    )
    assert audit_logs.status_code == 200
    assert any(item["objectId"] == "sec_pol_002" for item in audit_logs.json()["data"]["items"])


def test_security_policy_approval_id_must_match_url_policy(client, auth_headers):
    from app.db import SessionLocal
    from app.models import ApprovalRequest
    from app.id_gen import new_id

    approval_id = new_id("apr")

    with SessionLocal() as db:
        db.add(
            ApprovalRequest(
                id=approval_id,
                type="security_policy_change",
                risk_level="high",
                applicant_id="u001",
                status="approved",
                reason="mismatched policy approval",
                payload_snapshot={"policyId": "sec_pol_002", "status": "disabled", "config": {}, "description": "approved snapshot"},
            )
        )
        db.commit()

    mismatched = client.put(
        "/api/v1/astron-claw/security-policies/sec_pol_001",
        headers=auth_headers,
        json={"approvalId": approval_id},
    )
    assert mismatched.status_code == 422
    assert mismatched.json()["code"] == 400001
    assert mismatched.json()["data"]["field"] == "approvalId"


def test_p1_alert_creates_diagnosis_and_fix_closes_alert(client, auth_headers):
    alert = client.post(
        "/api/v1/astron-claw/alerts",
        headers=auth_headers,
        json={
            "level": "P1",
            "sourceType": "agent",
            "sourceId": "agt_test",
            "category": "runtime",
            "errorCode": "400003",
            "title": "沙箱会话失效",
            "rootCause": "session expired",
            "suggestion": "redeploy",
        },
    )
    assert alert.status_code == 200
    alert_data = alert.json()["data"]
    assert alert_data["diagnosisId"].startswith("diag_")

    diagnosis = client.get(f"/api/v1/astron-claw/diagnostics/{alert_data['diagnosisId']}", headers=auth_headers)
    assert diagnosis.status_code == 200
    assert diagnosis.json()["data"]["status"] == "open"

    fix = client.post(f"/api/v1/astron-claw/diagnostics/{alert_data['diagnosisId']}/fix", headers=auth_headers, json={})
    assert fix.status_code == 200
    fix_data = fix.json()["data"]
    assert fix_data["status"] == "success"
    assert fix_data["closedAlertCount"] == 1
    assert fix_data["fixTaskId"].startswith("fix_")
    assert fix_data["selfHealTaskId"].startswith("heal_")

    closed = client.get(f"/api/v1/astron-claw/alerts/{alert_data['id']}", headers=auth_headers)
    assert closed.json()["data"]["status"] == "closed"

    tasks = client.get("/api/v1/astron-claw/ops-tasks", headers=auth_headers, params={"taskType": "restart_agent"})
    assert tasks.status_code == 200
    task = next(item for item in tasks.json()["data"]["items"] if item["diagnosisId"] == alert_data["diagnosisId"])
    assert task["status"] == "success"
    assert task["result"]["closedAlertCount"] == 1
    assert task["id"] == fix_data["selfHealTaskId"]

    from app.db import SessionLocal
    from app.models import FixTask

    with SessionLocal() as db:
        stored_fix = db.get(FixTask, fix_data["fixTaskId"])
        assert stored_fix is not None
        assert stored_fix.diagnosis_id == alert_data["diagnosisId"]
        assert stored_fix.self_heal_task_id == task["id"]
        assert stored_fix.status == "success"
        assert stored_fix.result["closedAlertCount"] == 1


def test_alert_and_diagnosis_query_filters_match_frontend_contract(client, auth_headers):
    dep_agent = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "alert-filter-dep-agent", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    other_agent = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "alert-filter-other-agent", "departmentId": "dep001", "ownerId": "u001", "primaryModelId": "m001"},
    )
    dep_agent_id = dep_agent.json()["data"]["id"]
    other_agent_id = other_agent.json()["data"]["id"]

    dep_alert = client.post(
        "/api/v1/astron-claw/alerts",
        headers=auth_headers,
        json={"level": "P1", "sourceType": "agent", "sourceId": dep_agent_id, "category": "runtime", "title": "部门告警"},
    )
    assert dep_alert.status_code == 200
    other_alert = client.post(
        "/api/v1/astron-claw/alerts",
        headers=auth_headers,
        json={"level": "P2", "sourceType": "agent", "sourceId": other_agent_id, "category": "runtime", "title": "其他部门告警"},
    )
    assert other_alert.status_code == 200
    model_alert = client.post(
        "/api/v1/astron-claw/alerts",
        headers=auth_headers,
        json={"level": "P1", "sourceType": "model", "sourceId": "m001", "category": "model", "title": "模型告警"},
    )
    assert model_alert.status_code == 200

    filtered_alerts = client.get(
        "/api/v1/astron-claw/alerts",
        headers=auth_headers,
        params={"level": "P1", "sourceType": "agent", "departmentId": "dep002", "startTime": "2026-01-01T00:00:00+00:00"},
    )
    assert filtered_alerts.status_code == 200
    filtered_ids = {item["id"] for item in filtered_alerts.json()["data"]["items"]}
    assert dep_alert.json()["data"]["id"] in filtered_ids
    assert other_alert.json()["data"]["id"] not in filtered_ids
    assert model_alert.json()["data"]["id"] not in filtered_ids

    filtered_diagnostics = client.get("/api/v1/astron-claw/diagnostics", headers=auth_headers, params={"level": "P1", "objectType": "agent"})
    assert filtered_diagnostics.status_code == 200
    diagnostics = filtered_diagnostics.json()["data"]["items"]
    assert any(item["objectId"] == dep_agent_id for item in diagnostics)
    assert all(item["level"] == "P1" and item["objectType"] == "agent" for item in diagnostics)


def test_ops_task_high_risk_approval_and_failure_alert(client, auth_headers):
    direct = client.post(
        "/api/v1/astron-claw/ops-tasks",
        headers=auth_headers,
        json={"taskType": "cache_refresh", "targetType": "agent", "targetId": "agt_ops_normal"},
    )
    assert direct.status_code == 200
    assert direct.json()["data"]["status"] == "success"

    pending = client.post(
        "/api/v1/astron-claw/ops-tasks",
        headers=auth_headers,
        json={
            "taskType": "security_patch",
            "targetType": "agent",
            "targetId": "agt_ops_high",
            "reason": "security baseline remediation",
        },
    )
    assert pending.status_code == 200
    assert pending.json()["data"]["status"] == "pending_approval"
    approval_id = pending.json()["data"]["approvalId"]

    approved = client.post(f"/api/v1/astron-claw/approvals/{approval_id}/approve", headers=auth_headers, json={})
    assert approved.status_code == 200

    tasks = client.get("/api/v1/astron-claw/ops-tasks", headers=auth_headers, params={"taskType": "security_patch"})
    assert tasks.status_code == 200
    task = next(item for item in tasks.json()["data"]["items"] if item["approvalId"] == approval_id)
    assert task["status"] == "success"
    assert task["targetId"] == "agt_ops_high"

    failed = client.post(
        "/api/v1/astron-claw/ops-tasks",
        headers=auth_headers,
        json={
            "taskType": "model_probe_restore",
            "targetType": "model",
            "targetId": "m001",
            "forceFail": True,
            "errorMessage": "probe endpoint still unavailable",
        },
    )
    assert failed.status_code == 200
    failed_data = failed.json()["data"]
    assert failed_data["status"] == "failed"

    alerts = client.get("/api/v1/astron-claw/alerts", headers=auth_headers, params={"sourceType": "self_heal_task"})
    assert alerts.status_code == 200
    assert any(item["sourceId"] == failed_data["id"] and item["errorCode"] == "SELF_HEAL_FAILED" for item in alerts.json()["data"]["items"])

    audits = client.get("/api/v1/astron-claw/audit/operation-logs", headers=auth_headers, params={"module": "ops", "action": "create_task"})
    assert audits.status_code == 200
    assert any(item["objectId"] == failed_data["id"] for item in audits.json()["data"]["items"])


def test_alert_claim_process_close_flow_is_audited(client, auth_headers):
    alert = client.post(
        "/api/v1/astron-claw/alerts",
        headers=auth_headers,
        json={
            "level": "P2",
            "sourceType": "agent",
            "sourceId": "agt_alert_flow",
            "category": "runtime",
            "errorCode": "RUNTIME_WARN",
            "title": "运行指标异常",
            "suggestion": "check runtime metrics",
        },
    )
    assert alert.status_code == 200
    alert_id = alert.json()["data"]["id"]

    claimed = client.post(f"/api/v1/astron-claw/alerts/{alert_id}/claim", headers=auth_headers, json={})
    assert claimed.status_code == 200
    assert claimed.json()["data"]["status"] == "claimed"
    assert claimed.json()["data"]["ownerId"] == "u001"

    processing = client.post(
        f"/api/v1/astron-claw/alerts/{alert_id}/process",
        headers=auth_headers,
        json={"comment": "checking runtime", "detail": "operator is checking runtime metrics"},
    )
    assert processing.status_code == 200
    assert processing.json()["data"]["status"] == "processing"
    assert "checking runtime" in processing.json()["data"]["detail"]

    closed = client.post(
        f"/api/v1/astron-claw/alerts/{alert_id}/close",
        headers=auth_headers,
        json={"resolution": "runtime restored"},
    )
    assert closed.status_code == 200
    assert closed.json()["data"]["status"] == "closed"
    assert closed.json()["data"]["resolution"] == "runtime restored"
    assert closed.json()["data"]["updatedAt"]
    assert closed.json()["data"]["alertNo"] == alert_id
    assert closed.json()["data"]["sourceObject"] == {"type": "agent", "id": "agt_alert_flow"}
    assert closed.json()["data"]["impactScope"] == {"sourceType": "agent", "sourceId": "agt_alert_flow"}
    assert closed.json()["data"]["triggeredAt"]

    audit_logs = client.get("/api/v1/astron-claw/audit/operation-logs", headers=auth_headers, params={"module": "alert"})
    actions = {item["action"] for item in audit_logs.json()["data"]["items"] if item["objectId"] == alert_id}
    assert {"claim", "process", "close"}.issubset(actions)

    events = client.get(f"/api/v1/astron-claw/alerts/{alert_id}/events", headers=auth_headers)
    assert events.status_code == 200
    event_actions = [item["action"] for item in events.json()["data"]["items"]]
    assert {"create", "claim", "process", "close"}.issubset(set(event_actions))


def test_notification_center_counts_read_and_seat_expiration(client, auth_headers):
    alert = client.post(
        "/api/v1/astron-claw/alerts",
        headers=auth_headers,
        json={"level": "P1", "title": "通知中心告警", "sourceType": "agent", "sourceId": "agt_notify", "ownerId": "u001"},
    )
    assert alert.status_code == 200
    alert_id = alert.json()["data"]["id"]

    closed = client.post(
        f"/api/v1/astron-claw/alerts/{alert_id}/close",
        headers=auth_headers,
        json={"resolution": "handled"},
    )
    assert closed.status_code == 200

    approval = client.post(
        "/api/v1/astron-claw/approvals",
        headers=auth_headers,
        json={"type": "manual_check", "riskLevel": "high", "reason": "notify applicant", "payload": {"x": 1}},
    )
    assert approval.status_code == 200
    approval_data = approval.json()["data"]
    assert approval_data["steps"][0]["decision"] is None
    approved = client.post(f"/api/v1/astron-claw/approvals/{approval_data['id']}/approve", headers=auth_headers, json={"comment": "ok"})
    assert approved.status_code == 200
    assert approved.json()["data"]["steps"][0]["decision"] == "approved"
    assert approved.json()["data"]["steps"][0]["comment"] == "ok"

    expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    package = client.post(
        "/api/v1/astron-claw/seat-packages",
        headers=auth_headers,
        json={"name": "到期提醒席位包", "totalCount": 3, "expiresAt": expires_at},
    )
    assert package.status_code == 200
    scan = client.post("/api/v1/astron-claw/notifications/scan-seat-expirations", headers=auth_headers)
    assert scan.status_code == 200
    assert any(item["type"] == "seat_expiration" and item["detail"]["daysLeft"] == 7 for item in scan.json()["data"]["items"])

    summary = client.get("/api/v1/astron-claw/notifications/summary", headers=auth_headers)
    assert summary.status_code == 200
    summary_data = summary.json()["data"]
    assert summary_data["byType"]["alert_created"] >= 1
    assert summary_data["byType"]["alert_closed"] >= 1
    assert summary_data["byType"]["approval_decided"] >= 1
    assert summary_data["byType"]["seat_expiration"] >= 1

    notifications = client.get("/api/v1/astron-claw/notifications", headers=auth_headers, params={"status": "unread"})
    assert notifications.status_code == 200
    first_notification = notifications.json()["data"]["items"][0]
    read = client.post(f"/api/v1/astron-claw/notifications/{first_notification['id']}/read", headers=auth_headers)
    assert read.status_code == 200
    assert read.json()["data"]["status"] == "read"

    after = client.get("/api/v1/astron-claw/notifications/summary", headers=auth_headers)
    assert after.json()["data"]["unreadCount"] == summary_data["unreadCount"] - 1


def test_metric_samples_trigger_alert_rules_and_diagnosis(client, auth_headers):
    rule = client.post(
        "/api/v1/astron-claw/alert-rules",
        headers=auth_headers,
        json={
            "name": "节点离线告警",
            "metricName": "node_online",
            "operator": "<=",
            "threshold": 0,
            "level": "P1",
            "sourceType": "agent",
            "category": "runtime",
            "errorCode": "NODE_OFFLINE",
            "suggestion": "restart container",
        },
    )
    assert rule.status_code == 200
    rule_id = rule.json()["data"]["id"]

    collected = client.post(
        "/api/v1/astron-claw/monitor/metrics",
        headers=auth_headers,
        json={"sourceType": "agent", "sourceId": "agt_metric_rule", "metricName": "node_online", "value": 0, "dataSource": "claw_proxy"},
    )
    assert collected.status_code == 200
    data = collected.json()["data"]
    assert data["dataSource"] == "claw_proxy"
    assert len(data["triggeredAlerts"]) == 1
    alert = data["triggeredAlerts"][0]
    assert alert["errorCode"] == "NODE_OFFLINE"
    assert alert["level"] == "P1"

    metrics = client.get("/api/v1/astron-claw/monitor/metrics", headers=auth_headers, params={"sourceId": "agt_metric_rule", "metricName": "node_online"})
    assert metrics.status_code == 200
    assert metrics.json()["data"]["items"][0]["dataSource"] == "claw_proxy"

    events = client.get(f"/api/v1/astron-claw/alerts/{alert['id']}/events", headers=auth_headers)
    assert events.status_code == 200
    rule_hit = next(item for item in events.json()["data"]["items"] if item["action"] == "rule_hit")
    assert rule_hit["detail"]["ruleId"] == rule_id

    diagnostics = client.get("/api/v1/astron-claw/diagnostics", headers=auth_headers)
    assert any(item["objectId"] == "agt_metric_rule" and item["level"] == "P1" for item in diagnostics.json()["data"]["items"])

    listed_rules = client.get("/api/v1/astron-claw/alert-rules", headers=auth_headers, params={"metricName": "node_online"})
    assert any(item["id"] == rule_id for item in listed_rules.json()["data"]["items"])


def test_monitor_overview_uses_database_metrics(client, auth_headers):
    client.post(
        "/api/v1/astron-claw/dev/model-call-logs",
        json={"departmentId": "dep002", "agentId": "agt_monitor", "modelId": "m001", "tokens": 10, "latencyMs": 120, "cost": 0.1, "status": "success"},
    )
    client.post(
        "/api/v1/astron-claw/dev/model-call-logs",
        json={"departmentId": "dep002", "agentId": "agt_monitor", "modelId": "m001", "tokens": 20, "latencyMs": 80, "cost": 0.2, "status": "success"},
    )
    probe = client.post(
        "/api/v1/astron-claw/models/m001/probe",
        headers=auth_headers,
        json={"forceFail": True, "errorMessage": "monitor probe failure"},
    )
    assert probe.status_code == 200

    overview = client.get("/api/v1/astron-claw/monitor/overview", headers=auth_headers)
    assert overview.status_code == 200
    data = overview.json()["data"]
    assert data["dataSource"] == "database"
    assert data["todayCallCount"] >= 2
    assert data["avgLatencyMs"] == 100
    assert data["abnormalModelCount"] >= 1
    assert data["pendingAlertCount"] >= 1

    client.post("/api/v1/astron-claw/models/m001/enable", headers=auth_headers)


def test_cost_archive_summarizes_model_call_logs(client, auth_headers):
    log = client.post(
        "/api/v1/astron-claw/dev/model-call-logs",
        json={
            "departmentId": "dep002",
            "projectId": "prj_cost_test",
            "agentId": "agt_cost_test",
            "modelId": "m001",
            "tokens": 100,
            "cost": 1.5,
            "status": "success",
            "createdAt": "2026-07-02T10:00:00+00:00",
        },
    )
    assert log.status_code == 200
    other_day_log = client.post(
        "/api/v1/astron-claw/dev/model-call-logs",
        json={
            "departmentId": "dep002",
            "projectId": "prj_cost_test",
            "agentId": "agt_cost_test_other_day",
            "modelId": "m001",
            "tokens": 999,
            "cost": 9.99,
            "status": "success",
            "createdAt": "2026-07-03T10:00:00+00:00",
        },
    )
    assert other_day_log.status_code == 200
    archive = client.post("/api/v1/astron-claw/dev/cost/archive", json={"date": "2026-07-02"})
    assert archive.status_code == 200
    assert archive.json()["data"]["archivedStats"] >= 3

    by_model = client.get("/api/v1/astron-claw/cost/by-model", headers=auth_headers)
    assert by_model.status_code == 200
    items = by_model.json()["data"]["items"]
    assert all(item["dimensionType"] == "model" for item in items)
    model_item = next(item for item in items if item["dimensionId"] == "m001")
    assert model_item["callCount"] >= 1
    assert model_item["tokens"] >= 100
    assert model_item["modelCost"] >= 1.5

    by_project = client.get("/api/v1/astron-claw/cost/by-project", headers=auth_headers)
    assert by_project.status_code == 200
    project_item = next(item for item in by_project.json()["data"]["items"] if item["dimensionId"] == "prj_cost_test")
    assert project_item["dimensionType"] == "project"
    assert project_item["tokens"] >= 100
    assert project_item["modelCost"] >= 1.5
    assert all(item["dimensionId"] != "agt_cost_test_other_day" for item in client.get("/api/v1/astron-claw/cost/by-agent", headers=auth_headers).json()["data"]["items"])


def test_cost_archive_is_idempotent_for_same_date(client, auth_headers):
    log = client.post(
        "/api/v1/astron-claw/dev/model-call-logs",
        json={
            "departmentId": "dep002",
            "agentId": "agt_cost_idempotent",
            "modelId": "m001",
            "tokens": 123,
            "cost": 4.25,
            "status": "success",
            "createdAt": "2026-07-04T10:00:00+00:00",
        },
    )
    assert log.status_code == 200

    first_archive = client.post("/api/v1/astron-claw/dev/cost/archive", json={"date": "2026-07-04"})
    assert first_archive.status_code == 200
    assert first_archive.json()["data"]["archivedStats"] >= 3

    budget = client.post(
        "/api/v1/astron-claw/budgets",
        headers=auth_headers,
        json={
            "name": "成本归档幂等预算",
            "scopeType": "department",
            "scopeId": "dep002",
            "period": "monthly",
            "limitAmount": 100,
            "thresholdRatio": 0.9,
        },
    )
    assert budget.status_code == 200
    budget_id = budget.json()["data"]["id"]

    first_budget = client.post(f"/api/v1/astron-claw/budgets/{budget_id}/evaluate", headers=auth_headers)
    assert first_budget.status_code == 200
    first_used_amount = first_budget.json()["data"]["usedAmount"]

    second_archive = client.post("/api/v1/astron-claw/dev/cost/archive", json={"date": "2026-07-04"})
    assert second_archive.status_code == 200
    assert second_archive.json()["data"]["archivedStats"] == first_archive.json()["data"]["archivedStats"]

    by_agent = client.get("/api/v1/astron-claw/cost/by-agent", headers=auth_headers)
    assert by_agent.status_code == 200
    agent_items = [item for item in by_agent.json()["data"]["items"] if item["dimensionId"] == "agt_cost_idempotent"]
    assert len(agent_items) == 1
    assert agent_items[0]["callCount"] == 1
    assert agent_items[0]["tokens"] == 123
    assert agent_items[0]["modelCost"] == 4.25
    assert agent_items[0]["totalCost"] == 4.25

    second_budget = client.post(f"/api/v1/astron-claw/budgets/{budget_id}/evaluate", headers=auth_headers)
    assert second_budget.status_code == 200
    assert second_budget.json()["data"]["usedAmount"] == first_used_amount


def test_cost_reports_support_date_filters_periods_and_export(client, auth_headers):
    client.post(
        "/api/v1/astron-claw/dev/model-call-logs",
        json={
            "departmentId": "dep002",
            "agentId": "agt_cost_period",
            "modelId": "m001",
            "tokens": 50,
            "cost": 2.0,
            "status": "success",
            "createdAt": "2026-01-15T10:00:00+00:00",
        },
    )
    january = client.post("/api/v1/astron-claw/dev/cost/archive", json={"date": "2026-01-15"})
    assert january.status_code == 200
    client.post(
        "/api/v1/astron-claw/dev/model-call-logs",
        json={
            "departmentId": "dep002",
            "agentId": "agt_cost_period",
            "modelId": "m001",
            "tokens": 50,
            "cost": 2.0,
            "status": "success",
            "createdAt": "2026-02-03T10:00:00+00:00",
        },
    )
    february = client.post("/api/v1/astron-claw/dev/cost/archive", json={"date": "2026-02-03"})
    assert february.status_code == 200

    monthly = client.get(
        "/api/v1/astron-claw/cost/by-agent",
        headers=auth_headers,
        params={"startDate": "2026-01-01", "endDate": "2026-01-31", "period": "month"},
    )
    assert monthly.status_code == 200
    monthly_data = monthly.json()["data"]
    assert monthly_data["period"] == "month"
    item = next(item for item in monthly_data["items"] if item["dimensionId"] == "agt_cost_period")
    assert item["periodStart"] == "2026-01-01"
    assert item["periodEnd"] == "2026-01-31"
    assert item["callCount"] == 1
    assert item["tokens"] == 50
    assert item["modelCost"] == 2.0

    quarterly = client.get(
        "/api/v1/astron-claw/cost/by-agent",
        headers=auth_headers,
        params={"startDate": "2026-01-01", "endDate": "2026-03-31", "period": "quarter"},
    )
    assert quarterly.status_code == 200
    quarter_item = next(item for item in quarterly.json()["data"]["items"] if item["dimensionId"] == "agt_cost_period")
    assert quarter_item["periodStart"] == "2026-01-01"
    assert quarter_item["periodEnd"] == "2026-03-31"
    assert quarter_item["callCount"] == 2
    assert quarter_item["tokens"] == 100
    assert quarter_item["totalCost"] == 4.0

    exported = client.get(
        "/api/v1/astron-claw/cost/export",
        headers=auth_headers,
        params={"dimension": "agent", "startDate": "2026-01-01", "endDate": "2026-03-31", "period": "quarter"},
    )
    assert exported.status_code == 200
    report = exported.json()["data"]["report"]
    assert report["period"] == "quarter"
    assert report["dimension"] == "agent"
    exported_item = next(item for item in report["items"] if item["dimensionId"] == "agt_cost_period")
    assert exported_item["callCount"] == 2
    assert exported_item["totalCost"] == 4.0

    department_export = client.get(
        "/api/v1/astron-claw/cost/export",
        headers=auth_headers,
        params={"dimension": "department", "departmentId": "dep002", "startDate": "2026-01-01", "endDate": "2026-03-31"},
    )
    assert department_export.status_code == 200
    department_report = department_export.json()["data"]["report"]
    assert department_report["departmentId"] == "dep002"
    assert all(item["dimensionId"] == "dep002" for item in department_report["items"])
    assert department_export.json()["data"]["query"]["departmentId"] == "dep002"

    invalid_period = client.get("/api/v1/astron-claw/cost/by-agent", headers=auth_headers, params={"period": "year"})
    assert invalid_period.status_code == 422
    assert invalid_period.json()["data"]["field"] == "period"


def test_budget_evaluation_creates_threshold_and_overrun_alerts(client, auth_headers):
    rule = client.post(
        "/api/v1/astron-claw/cost-rules",
        headers=auth_headers,
        json={
            "name": "部门预算阈值",
            "ruleType": "budget_threshold",
            "scopeType": "department",
            "threshold": 0.8,
            "level": "P2",
            "config": {"period": "monthly"},
        },
    )
    assert rule.status_code == 200
    assert rule.json()["data"]["ruleType"] == "budget_threshold"

    listed_rules = client.get("/api/v1/astron-claw/cost-rules", headers=auth_headers, params={"ruleType": "budget_threshold"})
    assert listed_rules.status_code == 200
    assert any(item["name"] == "部门预算阈值" for item in listed_rules.json()["data"]["items"])

    budget = client.post(
        "/api/v1/astron-claw/budgets",
        headers=auth_headers,
        json={
            "name": "研发部月度预算",
            "scopeType": "department",
            "scopeId": "dep002",
            "period": "monthly",
            "limitAmount": 10,
            "thresholdRatio": 0.8,
            "ownerId": "u001",
        },
    )
    assert budget.status_code == 200
    budget_id = budget.json()["data"]["id"]

    warning = client.post(f"/api/v1/astron-claw/budgets/{budget_id}/evaluate", headers=auth_headers, json={"usedAmount": 8.5})
    assert warning.status_code == 200
    warning_data = warning.json()["data"]
    assert warning_data["evaluationStatus"] == "warning"
    assert warning_data["alertLevel"] == "P2"

    overrun = client.post(f"/api/v1/astron-claw/budgets/{budget_id}/evaluate", headers=auth_headers, json={"usedAmount": 12})
    assert overrun.status_code == 200
    overrun_data = overrun.json()["data"]
    assert overrun_data["evaluationStatus"] == "over_limit"
    assert overrun_data["alertLevel"] == "P1"

    alerts = client.get("/api/v1/astron-claw/alerts", headers=auth_headers, params={"sourceType": "budget"})
    assert alerts.status_code == 200
    alert_errors = {item["errorCode"] for item in alerts.json()["data"]["items"]}
    assert {"BUDGET_THRESHOLD", "BUDGET_EXCEEDED"} <= alert_errors

    budgets = client.get("/api/v1/astron-claw/budgets", headers=auth_headers, params={"scopeType": "department", "scopeId": "dep002"})
    assert budgets.status_code == 200
    listed_budget = next(item for item in budgets.json()["data"]["items"] if item["id"] == budget_id)
    assert listed_budget["usedAmount"] == 12
    assert listed_budget["usageRatio"] == 1.2

    audits = client.get("/api/v1/astron-claw/audit/operation-logs", headers=auth_headers, params={"module": "cost", "action": "budget_evaluate"})
    assert audits.status_code == 200
    assert any(item["objectId"] == budget_id for item in audits.json()["data"]["items"])


def test_resource_package_cost_archive_and_report(client, auth_headers):
    package = client.post(
        "/api/v1/astron-claw/resource-packages",
        headers=auth_headers,
        json={
            "name": "研发容器包",
            "packageType": "container",
            "targetType": "agent",
            "targetId": "agt_resource_cost",
            "cpu": 4,
            "memoryGb": 8,
            "gpu": 1,
            "storageGb": 100,
            "fixedDailyCost": 2.5,
        },
    )
    assert package.status_code == 200
    package_id = package.json()["data"]["id"]

    log = client.post(
        "/api/v1/astron-claw/dev/model-call-logs",
        json={
            "departmentId": "dep002",
            "agentId": "agt_resource_cost",
            "modelId": "m001",
            "tokens": 200,
            "cost": 3.5,
            "status": "success",
            "createdAt": "2026-07-03T10:00:00+00:00",
        },
    )
    assert log.status_code == 200

    archive = client.post("/api/v1/astron-claw/dev/cost/archive", json={"date": "2026-07-03"})
    assert archive.status_code == 200

    by_resource = client.get("/api/v1/astron-claw/cost/by-resource-package", headers=auth_headers)
    assert by_resource.status_code == 200
    item = next(i for i in by_resource.json()["data"]["items"] if i["dimensionId"] == package_id)
    assert item["dimensionType"] == "resource_package"
    assert item["dimensionName"] == "研发容器包"
    assert item["callCount"] == 1
    assert item["tokens"] == 200
    assert item["containerCost"] == 6.0
    assert item["totalCost"] == 6.0

    listed = client.get("/api/v1/astron-claw/resource-packages", headers=auth_headers, params={"targetType": "agent", "targetId": "agt_resource_cost"})
    assert listed.status_code == 200
    assert any(item["id"] == package_id for item in listed.json()["data"]["items"])

    audits = client.get("/api/v1/astron-claw/audit/operation-logs", headers=auth_headers, params={"module": "cost", "action": "create_resource_package"})
    assert audits.status_code == 200
    assert any(item["objectId"] == package_id for item in audits.json()["data"]["items"])


def test_model_gateway_quota_hit_and_success_log(client, auth_headers):
    quota = client.post(
        "/api/v1/astron-claw/model-quotas",
        headers=auth_headers,
        json={"scopeType": "agent", "scopeId": "agt_quota", "modelId": "m001", "dailyTokenLimit": 50},
    )
    assert quota.status_code == 200

    blocked = client.post(
        "/api/v1/astron-claw/dev/model-gateway/call",
        json={"agentId": "agt_quota", "departmentId": "dep002", "modelId": "m001", "tokens": 80},
    )
    assert blocked.status_code == 422
    assert blocked.json()["code"] == 422001
    assert blocked.json()["data"]["reason"] == "daily_token_limit"

    allowed = client.post(
        "/api/v1/astron-claw/dev/model-gateway/call",
        json={"agentId": "agt_quota", "departmentId": "dep002", "modelId": "m001", "tokens": 20},
    )
    assert allowed.status_code == 200
    assert allowed.json()["data"]["allowed"] is True
    assert allowed.json()["data"]["modelCallLogId"].startswith("mcl_")

    hits = client.get("/api/v1/astron-claw/model-policy-hits", headers=auth_headers)
    hit_types = {item["hitType"] for item in hits.json()["data"]}
    assert {"daily_token_limit", "route_selected"} <= hit_types


def test_model_gateway_qps_overload_queue_and_degrade(client, auth_headers):
    quota = client.post(
        "/api/v1/astron-claw/model-quotas",
        headers=auth_headers,
        json={"scopeType": "agent", "scopeId": "agt_overload", "modelId": "m001", "qpsLimit": 5, "dailyCallLimit": 2},
    )
    assert quota.status_code == 200

    queued = client.post(
        "/api/v1/astron-claw/dev/model-gateway/call",
        json={"agentId": "agt_overload", "departmentId": "dep002", "modelId": "m001", "tokens": 10, "currentQps": 9, "overloadStrategy": "queue"},
    )
    assert queued.status_code == 200
    assert queued.json()["data"]["decision"] == "queue"
    assert queued.json()["data"]["queued"] is True

    degraded = client.post(
        "/api/v1/astron-claw/dev/model-gateway/call",
        json={"agentId": "agt_overload", "departmentId": "dep002", "modelId": "m001", "tokens": 10, "callsToday": 2, "overloadStrategy": "degrade"},
    )
    assert degraded.status_code == 200
    assert degraded.json()["data"]["decision"] == "degrade"
    assert degraded.json()["data"]["degraded"] is True

    hits = client.get("/api/v1/astron-claw/model-policy-hits", headers=auth_headers, params={"modelId": "m001"})
    assert hits.status_code == 200
    hit_details = {item["hitType"]: item["detail"]["decision"] for item in hits.json()["data"] if item["hitType"] in {"qps_limit", "daily_call_limit"}}
    assert hit_details["qps_limit"] == "queue"
    assert hit_details["daily_call_limit"] == "degrade"

    logs = client.get("/api/v1/astron-claw/model-call-logs", headers=auth_headers, params={"agentId": "agt_overload"})
    statuses = {item["status"] for item in logs.json()["data"]["items"]}
    assert {"queued", "degraded"} <= statuses


def test_model_gateway_falls_back_to_backup_model(client, auth_headers):
    disabled = client.post("/api/v1/astron-claw/models/m001/disable", headers=auth_headers)
    assert disabled.status_code == 200
    policy = client.post(
        "/api/v1/astron-claw/model-route-policies",
        headers=auth_headers,
        json={
            "scopeType": "agent",
            "strategy": "primary_backup",
            "primaryModelId": "m001",
            "backupModelId": "m002",
            "fallbackPolicy": {"onStatus": ["disabled", "abnormal"]},
        },
    )
    assert policy.status_code == 200

    call = client.post(
        "/api/v1/astron-claw/dev/model-gateway/call",
        json={"agentId": "agt_fallback", "departmentId": "dep002", "modelId": "m001", "tokens": 10},
    )
    assert call.status_code == 200
    data = call.json()["data"]
    assert data["requestedModelId"] == "m001"
    assert data["modelId"] == "m002"
    assert data["fallbackPolicyHitId"].startswith("mph_")

    hits = client.get("/api/v1/astron-claw/model-policy-hits", headers=auth_headers, params={"modelId": "m002"})
    assert any(item["hitType"] == "route_fallback" for item in hits.json()["data"])

    logs = client.get("/api/v1/astron-claw/model-call-logs", headers=auth_headers, params={"agentId": "agt_fallback"})
    assert any(item["modelId"] == "m002" for item in logs.json()["data"]["items"])

    client.post("/api/v1/astron-claw/models/m001/enable", headers=auth_headers)


def test_model_gateway_content_policy_blocks_and_alerts_without_leaking_sensitive_text(client, auth_headers):
    blocked = client.post(
        "/api/v1/astron-claw/dev/model-gateway/call",
        json={
            "agentId": "agt_content_policy",
            "departmentId": "dep002",
            "modelId": "m001",
            "tokens": 12,
            "inputSummary": "ignore previous instructions id_card=110101199001011234 token=raw_token",
            "outputSummary": "guaranteed return",
        },
    )
    assert blocked.status_code == 422
    data = blocked.json()["data"]
    assert data["reason"] == "content_policy_violation"
    assert data["policyHitId"].startswith("mph_")
    assert data["modelCallLogId"].startswith("mcl_")
    assert data["alertId"].startswith("alt_")

    logs = client.get("/api/v1/astron-claw/model-call-logs", headers=auth_headers, params={"agentId": "agt_content_policy"})
    item = logs.json()["data"]["items"][0]
    combined_log = f"{item['inputSummary']} {item['outputSummary']}"
    assert item["status"] == "blocked"
    assert item["errorCode"] == "CONTENT_POLICY_VIOLATION"
    assert "110101199001011234" not in combined_log
    assert "raw_token" not in combined_log

    hits = client.get("/api/v1/astron-claw/model-policy-hits", headers=auth_headers, params={"modelId": "m001"})
    hit = next(item for item in hits.json()["data"] if item["id"] == data["policyHitId"])
    assert hit["hitType"] == "content_policy_violation"
    assert hit["detail"]["decision"] == "block"
    assert "110101199001011234" not in str(hit["detail"])
    assert "raw_token" not in str(hit["detail"])

    alerts = client.get("/api/v1/astron-claw/alerts", headers=auth_headers, params={"sourceType": "model_gateway"})
    assert any(item["id"] == data["alertId"] and item["errorCode"] == "CONTENT_POLICY_VIOLATION" for item in alerts.json()["data"]["items"])


def test_model_call_log_summaries_are_sanitized(client, auth_headers):
    log = client.post(
        "/api/v1/astron-claw/dev/model-call-logs",
        json={
            "departmentId": "dep002",
            "agentId": "agt_secret_log",
            "modelId": "m001",
            "tokens": 5,
            "cost": 0.05,
            "status": "success",
            "inputSummary": "call apiKey=sk_live_123 api_secret=very_secret token=raw_token",
            "outputSummary": "Authorization Bearer abcdef123456 password=hunter2",
        },
    )
    assert log.status_code == 200

    logs = client.get(
        "/api/v1/astron-claw/model-call-logs",
        headers=auth_headers,
        params={"agentId": "agt_secret_log"},
    )
    assert logs.status_code == 200
    item = logs.json()["data"]["items"][0]
    combined = f"{item['inputSummary']} {item['outputSummary']}"
    assert "sk_live_123" not in combined
    assert "very_secret" not in combined
    assert "raw_token" not in combined
    assert "abcdef123456" not in combined
    assert "hunter2" not in combined
    assert "[masked]" in combined


def test_log_and_policy_list_filters(client, auth_headers):
    client.post(
        "/api/v1/astron-claw/dev/model-call-logs",
        json={"departmentId": "dep002", "projectId": "prj_filter_a", "agentId": "agt_filter_a", "modelId": "m001", "tokens": 10, "cost": 0.1, "status": "success"},
    )
    client.post(
        "/api/v1/astron-claw/dev/model-call-logs",
        json={"departmentId": "dep001", "agentId": "agt_filter_b", "modelId": "m002", "tokens": 20, "cost": 0.2, "status": "failed"},
    )

    logs = client.get(
        "/api/v1/astron-claw/model-call-logs",
        headers=auth_headers,
        params={"modelId": "m001", "agentId": "agt_filter_a", "departmentId": "dep002", "projectId": "prj_filter_a", "status": "success"},
    )
    assert logs.status_code == 200
    items = logs.json()["data"]["items"]
    assert items
    assert all(item["modelId"] == "m001" and item["agentId"] == "agt_filter_a" and item["projectId"] == "prj_filter_a" for item in items)

    audit_logs = client.get(
        "/api/v1/astron-claw/audit/operation-logs",
        headers=auth_headers,
        params={"module": "model", "action": "create"},
    )
    assert audit_logs.status_code == 200
    assert all(item["module"] == "model" and item["action"] == "create" for item in audit_logs.json()["data"]["items"])

    bad_login = client.post("/api/v1/astron-claw/auth/login", json={"username": "admin", "password": "wrong"})
    assert bad_login.status_code == 401
    login_logs = client.get("/api/v1/astron-claw/audit/login-logs", headers=auth_headers, params={"status": "failed"})
    assert login_logs.status_code == 200
    assert any(item["result"] == "failed" for item in login_logs.json()["data"]["items"])
    assert all(item["result"] == "failed" for item in login_logs.json()["data"]["items"])

    quota = client.post(
        "/api/v1/astron-claw/model-quotas",
        headers=auth_headers,
        json={"scopeType": "agent", "scopeId": "agt_policy_filter", "modelId": "m001", "dailyTokenLimit": 5},
    )
    assert quota.status_code == 200
    client.post(
        "/api/v1/astron-claw/dev/model-gateway/call",
        json={"agentId": "agt_policy_filter", "departmentId": "dep002", "modelId": "m001", "tokens": 10},
    )
    policy_hits = client.get("/api/v1/astron-claw/model-policy-hits", headers=auth_headers, params={"modelId": "m001"})
    assert policy_hits.status_code == 200
    assert policy_hits.json()["data"]
    assert all(item["modelId"] == "m001" for item in policy_hits.json()["data"])


def test_seat_assignment_filters(client, auth_headers):
    create = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "seat-filter-agent", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    agent_id = create.json()["data"]["id"]

    by_agent = client.get("/api/v1/astron-claw/seat-assignments", headers=auth_headers, params={"agentId": agent_id})
    assert by_agent.status_code == 200
    assert by_agent.json()["data"]
    assert all(item["agentId"] == agent_id for item in by_agent.json()["data"])

    by_user = client.get("/api/v1/astron-claw/seat-assignments", headers=auth_headers, params={"userId": "u001"})
    assert by_user.status_code == 200
    assert all(item["assigneeId"] == "u001" for item in by_user.json()["data"])


def test_seat_assignment_transfer_updates_state_and_audit(client, auth_headers):
    package = client.post(
        "/api/v1/astron-claw/seat-packages",
        headers=auth_headers,
        json={"name": "transfer-seat-package", "totalCount": 1},
    )
    assert package.status_code == 200
    package_id = package.json()["data"]["id"]

    created = client.post(
        "/api/v1/astron-claw/seat-assignments",
        headers=auth_headers,
        json={"seatPackageId": package_id, "assigneeType": "user", "assigneeId": "user_a"},
    )
    assert created.status_code == 200
    assignment_id = created.json()["data"]["id"]

    packages_after_create = client.get("/api/v1/astron-claw/seat-packages", headers=auth_headers)
    pkg_after_create = next(item for item in packages_after_create.json()["data"] if item["id"] == package_id)
    assert pkg_after_create["usedCount"] == 1
    assert pkg_after_create["availableCount"] == 0

    transfer = client.post(
        f"/api/v1/astron-claw/seat-assignments/{assignment_id}/transfer",
        headers=auth_headers,
        json={"assigneeType": "user", "assigneeId": "user_b", "reason": "department transfer"},
    )
    assert transfer.status_code == 200
    assert transfer.json()["data"]["assigneeId"] == "user_b"

    by_user = client.get("/api/v1/astron-claw/seat-assignments", headers=auth_headers, params={"userId": "user_b"})
    assert any(item["id"] == assignment_id for item in by_user.json()["data"])

    audit_logs = client.get(
        "/api/v1/astron-claw/audit/operation-logs",
        headers=auth_headers,
        params={"module": "seat", "action": "transfer"},
    )
    assert audit_logs.status_code == 200
    assert any(item["objectId"] == assignment_id for item in audit_logs.json()["data"]["items"])

    events_after_transfer = client.get(
        "/api/v1/astron-claw/seat-events",
        headers=auth_headers,
        params={"assignmentId": assignment_id},
    )
    assert events_after_transfer.status_code == 200
    event_items = events_after_transfer.json()["data"]["items"]
    event_types = {item["eventType"] for item in event_items}
    assert {"assign", "transfer"} <= event_types
    transfer_event = next(item for item in event_items if item["eventType"] == "transfer")
    assert transfer_event["before"]["assigneeId"] == "user_a"
    assert transfer_event["after"]["assigneeId"] == "user_b"
    assert transfer_event["reason"] == "department transfer"

    deleted = client.delete(f"/api/v1/astron-claw/seat-assignments/{assignment_id}", headers=auth_headers)
    assert deleted.status_code == 200
    packages_after_delete = client.get("/api/v1/astron-claw/seat-packages", headers=auth_headers)
    pkg_after_delete = next(item for item in packages_after_delete.json()["data"] if item["id"] == package_id)
    assert pkg_after_delete["usedCount"] == 0
    assert pkg_after_delete["availableCount"] == 1

    events_after_delete = client.get(
        "/api/v1/astron-claw/seat-events",
        headers=auth_headers,
        params={"assignmentId": assignment_id, "eventType": "reclaim"},
    )
    assert events_after_delete.status_code == 200
    assert events_after_delete.json()["data"]["items"][0]["before"]["assigneeId"] == "user_b"


def test_departed_user_reclaims_seats_and_revokes_sessions(client, auth_headers):
    from app.core.security import hash_password
    from app.db import SessionLocal
    from app.models import User

    with SessionLocal() as db:
        db.add(
            User(
                id="u_departed",
                username="departed_user",
                password_hash=hash_password("Departed@123456"),
                name="Departed User",
                department_id="dep002",
                status="active",
                seat_status="unassigned",
            )
        )
        db.commit()

    package = client.post(
        "/api/v1/astron-claw/seat-packages",
        headers=auth_headers,
        json={"name": "departed-seat-package", "totalCount": 1},
    )
    package_id = package.json()["data"]["id"]
    assigned = client.post(
        "/api/v1/astron-claw/seat-assignments",
        headers=auth_headers,
        json={"seatPackageId": package_id, "assigneeType": "user", "assigneeId": "u_departed"},
    )
    assert assigned.status_code == 200

    user_login = client.post(
        "/api/v1/astron-claw/auth/login",
        json={"username": "departed_user", "password": "Departed@123456"},
    )
    assert user_login.status_code == 200
    user_headers = {"Authorization": f"Bearer {user_login.json()['data']['accessToken']}"}
    assert client.get("/api/v1/astron-claw/me", headers=user_headers).status_code == 200

    departed = client.put(
        "/api/v1/astron-claw/org/users/u_departed/status",
        headers=auth_headers,
        json={"status": "departed", "reason": "employee left"},
    )
    assert departed.status_code == 200
    assert departed.json()["data"]["status"] == "departed"
    assert departed.json()["data"]["seatStatus"] == "unassigned"
    assert departed.json()["data"]["reclaimedSeats"][0]["status"] == "reclaimed"

    assert client.get("/api/v1/astron-claw/me", headers=user_headers).status_code == 401
    relogin = client.post(
        "/api/v1/astron-claw/auth/login",
        json={"username": "departed_user", "password": "Departed@123456"},
    )
    assert relogin.status_code == 401
    assert relogin.json()["code"] == 401003

    package_after = client.get("/api/v1/astron-claw/seat-packages", headers=auth_headers)
    pkg = next(item for item in package_after.json()["data"] if item["id"] == package_id)
    assert pkg["usedCount"] == 0
    assert pkg["availableCount"] == 1

    assignments = client.get("/api/v1/astron-claw/seat-assignments", headers=auth_headers, params={"userId": "u_departed"})
    assert assignments.json()["data"][0]["status"] == "reclaimed"

    audit_logs = client.get(
        "/api/v1/astron-claw/audit/operation-logs",
        headers=auth_headers,
        params={"module": "seat", "action": "reclaim"},
    )
    assert any(item["objectId"] == assigned.json()["data"]["id"] for item in audit_logs.json()["data"]["items"])


def test_personal_share_consumes_and_reclaims_seat(client, auth_headers):
    from app.core.security import hash_password
    from app.db import SessionLocal
    from app.models import User

    with SessionLocal() as db:
        db.add(
            User(
                id="u_share_target",
                username="share_target",
                password_hash=hash_password("Share@123456"),
                name="Share Target",
                department_id="dep002",
                status="active",
                seat_status="unassigned",
            )
        )
        db.commit()

    create = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "share-seat-agent", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    agent_id = create.json()["data"]["id"]
    packages_before = client.get("/api/v1/astron-claw/seat-packages", headers=auth_headers).json()["data"]
    default_pkg_before = next(item for item in packages_before if item["id"] == "seat_pkg_001")

    share = client.post(
        f"/api/v1/astron-claw/agents/{agent_id}/share-grants",
        headers=auth_headers,
        json={"scopeType": "user", "scopeId": "u_share_target", "permission": "use", "reason": "trial use"},
    )
    assert share.status_code == 200
    grant_id = share.json()["data"]["id"]
    assert share.json()["data"]["status"] == "active"

    packages_after_share = client.get("/api/v1/astron-claw/seat-packages", headers=auth_headers).json()["data"]
    default_pkg_after_share = next(item for item in packages_after_share if item["id"] == "seat_pkg_001")
    assert default_pkg_after_share["usedCount"] == default_pkg_before["usedCount"] + 1

    assignments = client.get("/api/v1/astron-claw/seat-assignments", headers=auth_headers, params={"userId": "u_share_target"})
    assert any(item["agentId"] == agent_id and item["status"] == "active" for item in assignments.json()["data"])

    revoked = client.delete(f"/api/v1/astron-claw/agents/{agent_id}/share-grants/{grant_id}", headers=auth_headers)
    assert revoked.status_code == 200
    assert revoked.json()["data"]["status"] == "revoked"
    assert revoked.json()["data"]["reclaimedSeats"][0]["status"] == "reclaimed"

    packages_after_revoke = client.get("/api/v1/astron-claw/seat-packages", headers=auth_headers).json()["data"]
    default_pkg_after_revoke = next(item for item in packages_after_revoke if item["id"] == "seat_pkg_001")
    assert default_pkg_after_revoke["usedCount"] == default_pkg_before["usedCount"]

    audit_logs = client.get(
        "/api/v1/astron-claw/audit/operation-logs",
        headers=auth_headers,
        params={"module": "share", "action": "revoke"},
    )
    assert any(item["objectId"] == grant_id for item in audit_logs.json()["data"]["items"])


def test_department_share_requires_approval_and_uses_frozen_payload(client, auth_headers):
    create = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "department-share-agent", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    agent_id = create.json()["data"]["id"]

    requested = client.post(
        f"/api/v1/astron-claw/agents/{agent_id}/share-grants",
        headers=auth_headers,
        json={"scopeType": "department", "scopeId": "dep002", "permission": "view_config", "reason": "department trial"},
    )
    assert requested.status_code == 200
    assert requested.json()["data"]["status"] == "pending_approval"
    approval_id = requested.json()["data"]["approvalId"]

    assert client.get(f"/api/v1/astron-claw/agents/{agent_id}/share-grants", headers=auth_headers).json()["data"] == []

    from app.db import SessionLocal
    from app.models import ApprovalRequest

    with SessionLocal() as db:
        approval = db.get(ApprovalRequest, approval_id)
        snapshot = dict(approval.payload_snapshot)
        snapshot["scopeId"] = "dep003"
        approval.payload_snapshot = snapshot
        db.commit()

    approved = client.post(f"/api/v1/astron-claw/approvals/{approval_id}/approve", headers=auth_headers, json={})
    assert approved.status_code == 200

    grants = client.get(f"/api/v1/astron-claw/agents/{agent_id}/share-grants", headers=auth_headers)
    assert grants.status_code == 200
    assert grants.json()["data"][0]["scopeType"] == "department"
    assert grants.json()["data"][0]["scopeId"] == "dep003"
    assert grants.json()["data"][0]["permission"] == "view_config"


def test_expired_personal_share_is_reclaimed_when_listed(client, auth_headers):
    from app.core.security import hash_password
    from app.db import SessionLocal
    from app.models import User

    with SessionLocal() as db:
        db.add(
            User(
                id="u_expired_share",
                username="expired_share",
                password_hash=hash_password("Share@123456"),
                name="Expired Share",
                department_id="dep002",
                status="active",
                seat_status="unassigned",
            )
        )
        db.commit()

    create = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={"name": "expired-share-agent", "departmentId": "dep002", "ownerId": "u001", "primaryModelId": "m001"},
    )
    agent_id = create.json()["data"]["id"]
    before = next(item for item in client.get("/api/v1/astron-claw/seat-packages", headers=auth_headers).json()["data"] if item["id"] == "seat_pkg_001")

    share = client.post(
        f"/api/v1/astron-claw/agents/{agent_id}/share-grants",
        headers=auth_headers,
        json={
            "scopeType": "user",
            "scopeId": "u_expired_share",
            "permission": "use",
            "expiresAt": "2000-01-01T00:00:00",
            "reason": "temporary access",
        },
    )
    assert share.status_code == 200
    grant_id = share.json()["data"]["id"]
    during = next(item for item in client.get("/api/v1/astron-claw/seat-packages", headers=auth_headers).json()["data"] if item["id"] == "seat_pkg_001")
    assert during["usedCount"] == before["usedCount"] + 1

    listed = client.get(f"/api/v1/astron-claw/agents/{agent_id}/share-grants", headers=auth_headers)
    assert listed.status_code == 200
    grant = next(item for item in listed.json()["data"] if item["id"] == grant_id)
    assert grant["status"] == "expired"

    after = next(item for item in client.get("/api/v1/astron-claw/seat-packages", headers=auth_headers).json()["data"] if item["id"] == "seat_pkg_001")
    assert after["usedCount"] == before["usedCount"]

    assignments = client.get("/api/v1/astron-claw/seat-assignments", headers=auth_headers, params={"userId": "u_expired_share"})
    assert assignments.json()["data"][0]["status"] == "reclaimed"

    audit_logs = client.get(
        "/api/v1/astron-claw/audit/operation-logs",
        headers=auth_headers,
        params={"module": "share", "action": "expire"},
    )
    assert any(item["objectId"] == grant_id for item in audit_logs.json()["data"]["items"])


def test_knowledge_file_parse_task_flow(client, auth_headers):
    created = client.post(
        "/api/v1/astron-claw/knowledge-bases/kb001/files",
        headers=auth_headers,
        json={"filename": "policy.md", "fileType": "md", "sizeBytes": 128},
    )
    assert created.status_code == 200
    file_id = created.json()["data"]["id"]
    assert created.json()["data"]["parseTaskId"].startswith("kpt_")

    files = client.get("/api/v1/astron-claw/knowledge-bases/kb001/files", headers=auth_headers)
    item = next(row for row in files.json()["data"] if row["id"] == file_id)
    assert item["status"] == "indexed"
    assert item["parseTask"]["status"] == "success"
    assert item["parseTask"]["phase"] == "indexed"

    reindex = client.post(f"/api/v1/astron-claw/knowledge-files/{file_id}/reindex", headers=auth_headers)
    assert reindex.status_code == 200
    assert reindex.json()["data"]["status"] == "parsing"
    files_after = client.get("/api/v1/astron-claw/knowledge-bases/kb001/files", headers=auth_headers)
    item_after = next(row for row in files_after.json()["data"] if row["id"] == file_id)
    assert item_after["status"] == "indexed"


def test_knowledge_file_upload_security_validation(client, auth_headers):
    kb = client.post(
        "/api/v1/astron-claw/knowledge-bases",
        headers=auth_headers,
        json={"name": "文件安全知识库", "scope": "department", "departmentId": "dep002"},
    )
    assert kb.status_code == 200
    kb_id = kb.json()["data"]["id"]

    valid = client.post(
        f"/api/v1/astron-claw/knowledge-bases/{kb_id}/files",
        headers=auth_headers,
        json={"filename": "policy.pdf", "fileType": "pdf", "sizeBytes": 1024, "contentPreview": "policy document"},
    )
    assert valid.status_code == 200
    assert valid.json()["data"]["status"] == "uploaded"

    files = client.get(f"/api/v1/astron-claw/knowledge-bases/{kb_id}/files", headers=auth_headers)
    valid_item = next(item for item in files.json()["data"] if item["id"] == valid.json()["data"]["id"])
    assert valid_item["status"] == "indexed"
    assert valid_item["parseTask"]["status"] == "success"

    cases = [
        ({"filename": "tool.exe", "fileType": "exe", "sizeBytes": 100}, "unsupported file type"),
        ({"filename": "empty.md", "fileType": "md", "sizeBytes": 0}, "file size must be positive"),
        ({"filename": "large.pdf", "fileType": "pdf", "sizeBytes": 50 * 1024 * 1024 + 1}, "file size exceeds 50MB limit"),
        ({"filename": "virus.txt", "fileType": "txt", "sizeBytes": 100, "contentPreview": "EICAR test file"}, "virus scan failed"),
        ({"filename": "secret.md", "fileType": "md", "sizeBytes": 100, "contentPreview": "api_key=raw-secret"}, "sensitive content detected"),
    ]
    rejected_ids = []
    for payload, reason in cases:
        response = client.post(f"/api/v1/astron-claw/knowledge-bases/{kb_id}/files", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status"] == "failed"
        assert data["parseError"] == reason
        rejected_ids.append(data["id"])

    listed = client.get(f"/api/v1/astron-claw/knowledge-bases/{kb_id}/files", headers=auth_headers)
    rejected = [item for item in listed.json()["data"] if item["id"] in rejected_ids]
    assert {item["parseTask"]["status"] for item in rejected} == {"failed"}
    assert {item["parseTask"]["phase"] for item in rejected} == {"validating"}

    audits = client.get("/api/v1/astron-claw/audit/operation-logs", headers=auth_headers, params={"module": "knowledge", "action": "upload_rejected"})
    assert audits.status_code == 200
    assert len(audits.json()["data"]["items"]) >= len(cases)


def test_delete_referenced_knowledge_file_requires_unbind(client, auth_headers):
    kb = client.post(
        "/api/v1/astron-claw/knowledge-bases",
        headers=auth_headers,
        json={"name": "referenced-kb", "scope": "department", "departmentId": "dep002"},
    )
    assert kb.status_code == 200
    kb_id = kb.json()["data"]["id"]

    create_agent = client.post(
        "/api/v1/astron-claw/agents",
        headers=auth_headers,
        json={
            "name": "knowledge-reference-agent",
            "departmentId": "dep002",
            "ownerId": "u001",
            "primaryModelId": "m001",
            "knowledgeBaseIds": [kb_id],
        },
    )
    assert create_agent.status_code == 200
    agent_id = create_agent.json()["data"]["id"]

    created_file = client.post(
        f"/api/v1/astron-claw/knowledge-bases/{kb_id}/files",
        headers=auth_headers,
        json={"filename": "referenced.md", "fileType": "md", "sizeBytes": 64},
    )
    assert created_file.status_code == 200
    file_id = created_file.json()["data"]["id"]

    blocked = client.delete(f"/api/v1/astron-claw/knowledge-files/{file_id}", headers=auth_headers)
    assert blocked.status_code == 409
    assert blocked.json()["code"] == 409001
    refs = blocked.json()["data"]["references"]
    assert any(ref["agentId"] == agent_id for ref in refs)

    unbind = client.delete(f"/api/v1/astron-claw/agents/{agent_id}/knowledge-bases/{kb_id}/bind", headers=auth_headers)
    assert unbind.status_code == 200
    deleted = client.delete(f"/api/v1/astron-claw/knowledge-files/{file_id}", headers=auth_headers)
    assert deleted.status_code == 200
    files = client.get(f"/api/v1/astron-claw/knowledge-bases/{kb_id}/files", headers=auth_headers)
    assert all(item["id"] != file_id for item in files.json()["data"])


def test_knowledge_grants_control_visibility_and_binding(client, auth_headers):
    from app.core.security import hash_password
    from app.db import SessionLocal
    from app.models import Permission, Role, RolePermission, User, UserRole

    with SessionLocal() as db:
        if not db.get(Role, "dep003_reader"):
            db.add(Role(id="dep003_reader", name="Dep003 Reader", data_scope={"type": "department", "departmentIds": ["dep003"]}, status="active"))
        if not db.get(Permission, "agent:create"):
            db.add(Permission(code="agent:create", module="agent", page="agents", action="create", risk_level="normal"))
        if not db.get(User, "u_kb_reader"):
            db.add(User(id="u_kb_reader", username="kb_reader", password_hash=hash_password("Reader@123456"), name="KB Reader", department_id="dep003", status="active"))
            db.add(UserRole(user_id="u_kb_reader", role_id="dep003_reader"))
            db.add(RolePermission(role_id="dep003_reader", permission_code="agent:create"))
        db.commit()

    login = client.post("/api/v1/astron-claw/auth/login", json={"username": "kb_reader", "password": "Reader@123456"})
    assert login.status_code == 200
    reader_headers = {"Authorization": f"Bearer {login.json()['data']['accessToken']}"}

    kb = client.post(
        "/api/v1/astron-claw/knowledge-bases",
        headers=auth_headers,
        json={"name": "部门隔离知识库", "scope": "department", "departmentId": "dep002"},
    )
    assert kb.status_code == 200
    kb_id = kb.json()["data"]["id"]

    invisible = client.get("/api/v1/astron-claw/knowledge-bases", headers=reader_headers)
    assert invisible.status_code == 200
    assert all(item["id"] != kb_id for item in invisible.json()["data"])

    forbidden_agent = client.post(
        "/api/v1/astron-claw/agents",
        headers=reader_headers,
        json={"name": "未授权知识助手", "departmentId": "dep003", "ownerId": "u_kb_reader", "primaryModelId": "m001", "knowledgeBaseIds": [kb_id]},
    )
    assert forbidden_agent.status_code == 403
    denied = client.get(
        "/api/v1/astron-claw/audit/operation-logs",
        headers=auth_headers,
        params={"module": "security", "action": "permission_denied", "pageSize": 100},
    )
    assert denied.status_code == 200
    assert any(row["actor"]["id"] == "u_kb_reader" and row["objectId"] == "knowledge:bind" for row in denied.json()["data"]["items"])

    grant = client.post(
        f"/api/v1/astron-claw/knowledge-bases/{kb_id}/grants",
        headers=auth_headers,
        json={"scopeType": "department", "scopeId": "dep003", "permission": "read"},
    )
    assert grant.status_code == 200

    visible = client.get("/api/v1/astron-claw/knowledge-bases", headers=reader_headers)
    assert any(item["id"] == kb_id for item in visible.json()["data"])

    allowed_agent = client.post(
        "/api/v1/astron-claw/agents",
        headers=reader_headers,
        json={"name": "授权知识助手", "departmentId": "dep003", "ownerId": "u_kb_reader", "primaryModelId": "m001", "knowledgeBaseIds": [kb_id]},
    )
    assert allowed_agent.status_code == 200


def test_memory_share_requires_approval_and_updates_request(client, auth_headers):
    from app.core.security import hash_password
    from app.db import SessionLocal
    from app.models import Role, User, UserRole

    with SessionLocal() as db:
        if not db.get(Role, "memory_plain"):
            db.add(Role(id="memory_plain", name="Memory Plain", data_scope={"type": "self", "departmentIds": ["dep002"]}, status="active"))
        if not db.get(User, "u_memory_plain"):
            db.add(User(id="u_memory_plain", username="memory_plain", password_hash=hash_password("Memory@123456"), name="Memory Plain", department_id="dep002", status="active"))
            db.add(UserRole(user_id="u_memory_plain", role_id="memory_plain"))
        db.commit()

    plain_login = client.post("/api/v1/astron-claw/auth/login", json={"username": "memory_plain", "password": "Memory@123456"})
    assert plain_login.status_code == 200
    plain_headers = {"Authorization": f"Bearer {plain_login.json()['data']['accessToken']}"}

    memory = client.post(
        "/api/v1/astron-claw/memories",
        headers=auth_headers,
        json={"scope": "personal", "title": "核保经验", "contentSummary": "underwriting notes"},
    )
    assert memory.status_code == 200
    memory_id = memory.json()["data"]["id"]

    plain_memories = client.get("/api/v1/astron-claw/memories", headers=plain_headers)
    assert plain_memories.status_code == 200
    assert all(item["id"] != memory_id for item in plain_memories.json()["data"]["items"])
    assert client.put(f"/api/v1/astron-claw/memories/{memory_id}", headers=plain_headers, json={"title": "tampered"}).status_code == 403
    assert client.delete(f"/api/v1/astron-claw/memories/{memory_id}", headers=plain_headers).status_code == 403
    assert client.post(f"/api/v1/astron-claw/memories/{memory_id}/share", headers=plain_headers, json={"scope": "enterprise"}).status_code == 403
    denied = client.get(
        "/api/v1/astron-claw/audit/operation-logs",
        headers=auth_headers,
        params={"module": "security", "action": "permission_denied", "pageSize": 100},
    )
    assert denied.status_code == 200
    denied_codes = {row["objectId"] for row in denied.json()["data"]["items"] if row["actor"]["id"] == "u_memory_plain"}
    assert {"memory:manage", "memory:share"} <= denied_codes

    share = client.post(
        f"/api/v1/astron-claw/memories/{memory_id}/share",
        headers=auth_headers,
        json={"scope": "enterprise", "reason": "share best practice"},
    )
    assert share.status_code == 200
    share_data = share.json()["data"]
    assert share_data["status"] == "pending_review"
    approval_id = share_data["approvalId"]

    pending = client.get("/api/v1/astron-claw/memory-share-requests", headers=auth_headers, params={"memoryId": memory_id})
    assert pending.status_code == 200
    assert pending.json()["data"]["items"][0]["status"] == "pending"

    approved = client.post(f"/api/v1/astron-claw/approvals/{approval_id}/approve", headers=auth_headers, json={})
    assert approved.status_code == 200

    requests = client.get("/api/v1/astron-claw/memory-share-requests", headers=auth_headers, params={"memoryId": memory_id})
    item = requests.json()["data"]["items"][0]
    assert item["status"] == "approved"
    assert item["targetScope"] == "enterprise"

    memories = client.get("/api/v1/astron-claw/memories", headers=auth_headers, params={"scope": "enterprise", "keyword": "核保"})
    assert memories.json()["data"]["total"] >= 1
    shared = next(item for item in memories.json()["data"]["items"] if item["id"] == memory_id)
    assert shared["scope"] == "enterprise"


def test_failed_inspection_creates_alert_and_diagnosis(client, auth_headers):
    task = client.post(
        "/api/v1/astron-claw/inspection-tasks",
        headers=auth_headers,
        json={"name": "失败巡检", "scope": {"type": "agent"}},
    )
    assert task.status_code == 200
    run = client.post(
        f"/api/v1/astron-claw/inspection-tasks/{task.json()['data']['id']}/run",
        headers=auth_headers,
        json={
            "items": [
                {"name": "database", "status": "passed", "objectType": "database", "objectId": "db"},
                {
                    "name": "model_gateway",
                    "status": "failed",
                    "level": "P1",
                    "objectType": "model",
                    "objectId": "m001",
                    "errorCode": "MODEL_GATEWAY_FAILED",
                    "rootCause": "probe failed",
                    "suggestion": "switch backup model",
                },
            ]
        },
    )
    assert run.status_code == 200
    assert run.json()["data"]["status"] == "failed"
    run_id = run.json()["data"]["runId"]
    detail = client.get(f"/api/v1/astron-claw/inspection-runs/{run_id}", headers=auth_headers)
    assert detail.status_code == 200
    detail_data = detail.json()["data"]
    assert detail_data["summary"]["failed"] == 1
    assert detail_data["stats"] == {"total": 2, "passed": 1, "warning": 0, "failed": 1}
    failed_item = next(item for item in detail_data["items"] if item["status"] == "failed")
    assert failed_item["errorCode"] == "MODEL_GATEWAY_FAILED"
    assert failed_item["rootCause"] == "probe failed"

    export = client.get(f"/api/v1/astron-claw/inspection-runs/{run_id}/export", headers=auth_headers)
    assert export.status_code == 200
    export_data = export.json()["data"]
    assert export_data["taskId"].startswith("exp_")
    assert export_data["report"]["stats"]["failed"] == 1
    assert export_data["report"]["items"][1]["suggestion"] == "switch backup model"

    alerts = client.get("/api/v1/astron-claw/alerts?sourceType=model", headers=auth_headers)
    assert any(item["errorCode"] == "MODEL_GATEWAY_FAILED" for item in alerts.json()["data"]["items"])

    diagnostics = client.get("/api/v1/astron-claw/diagnostics", headers=auth_headers, params={"level": "P1", "objectType": "model"})
    assert diagnostics.status_code == 200
    diagnosis = next(item for item in diagnostics.json()["data"]["items"] if item["objectId"] == "m001" and item["summary"] == "model_gateway")
    fixed = client.post(f"/api/v1/astron-claw/diagnostics/{diagnosis['id']}/fix", headers=auth_headers, json={})
    assert fixed.status_code == 200
    assert fixed.json()["data"]["updatedInspectionItemCount"] == 1

    fixed_detail = client.get(f"/api/v1/astron-claw/inspection-runs/{run_id}", headers=auth_headers)
    assert fixed_detail.status_code == 200
    fixed_data = fixed_detail.json()["data"]
    assert fixed_data["status"] == "success"
    assert fixed_data["stats"] == {"total": 2, "passed": 2, "warning": 0, "failed": 0}
    fixed_item = next(item for item in fixed_data["items"] if item["name"] == "model_gateway")
    assert fixed_item["status"] == "passed"
    assert "一键修复" in fixed_item["detail"]


def test_default_inspection_covers_required_scopes_and_export_formats(client, auth_headers):
    task = client.post(
        "/api/v1/astron-claw/inspection-tasks",
        headers=auth_headers,
        json={"name": "全域默认巡检", "scope": {"type": "global", "mode": "scheduled"}},
    )
    assert task.status_code == 200

    run = client.post(f"/api/v1/astron-claw/inspection-tasks/{task.json()['data']['id']}/run", headers=auth_headers, json={})
    assert run.status_code == 200
    run_id = run.json()["data"]["runId"]

    detail = client.get(f"/api/v1/astron-claw/inspection-runs/{run_id}", headers=auth_headers)
    assert detail.status_code == 200
    data = detail.json()["data"]
    assert data["status"] == "warning"
    assert data["stats"]["total"] == 10
    assert data["stats"]["warning"] == 1
    assert data["summary"]["warning"] == 1
    object_types = {item["objectType"] for item in data["items"]}
    assert {"server", "network", "container", "agent", "model", "storage", "database", "channel", "certificate", "backup"} <= object_types
    assert all(item["suggestion"] for item in data["items"])

    for report_format, extension in [("excel", ".xlsx"), ("html", ".html"), ("pdf", ".pdf")]:
        exported = client.get(
            f"/api/v1/astron-claw/inspection-runs/{run_id}/export",
            headers=auth_headers,
            params={"format": report_format},
        )
        assert exported.status_code == 200
        export_data = exported.json()["data"]
        assert export_data["format"] == report_format
        assert export_data["downloadUrl"].endswith(extension)
        assert export_data["report"]["stats"]["total"] == 10

    invalid = client.get(
        f"/api/v1/astron-claw/inspection-runs/{run_id}/export",
        headers=auth_headers,
        params={"format": "docx"},
    )
    assert invalid.status_code == 422
    assert invalid.json()["data"]["field"] == "format"
    diagnostics = client.get("/api/v1/astron-claw/diagnostics", headers=auth_headers)
    assert any(item["summary"] == "model_gateway" for item in diagnostics.json()["data"]["items"])
