from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.id_gen import new_id
from app.models import Alert, LlmModel, ModelCallLog, ModelPolicyHit, ModelQuotaPolicy, ModelRoutePolicy


SENSITIVE_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(api[_-]?secret\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(password\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(secret\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(token\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(id[_-]?card\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(bank[_-]?card\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(bearer\s+)[a-z0-9._~+/-]+=*"),
]

CONTENT_POLICY_PATTERNS = [
    ("privacy", re.compile(r"(?i)\b(id[_ -]?card|ssn|身份证|银行卡|bank[_ -]?card)\b")),
    ("financial_advice", re.compile(r"(?i)\b(guaranteed return|稳赚|保本高收益|内幕消息)\b")),
    ("prompt_injection", re.compile(r"(?i)\b(ignore previous instructions|system prompt|越狱提示)\b")),
]


def sanitize_summary(value: object, default: str) -> str:
    text = str(value if value is not None else default)
    for pattern in SENSITIVE_PATTERNS:
        text = pattern.sub("[masked]", text)
    return text[:500]


def content_policy_findings(*values: object) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for value in values:
        text = str(value or "")
        for category, pattern in CONTENT_POLICY_PATTERNS:
            if pattern.search(text):
                findings.append({"category": category, "action": "block"})
                break
    return findings


def simulate_model_call(db: Session, payload: dict) -> dict:
    requested_model_id = payload.get("modelId", "m001")
    route = _find_route_policy(db, requested_model_id, payload)
    model_id = route.primary_model_id if route and route.primary_model_id else requested_model_id
    selected_model_id = model_id
    route_hit = None
    primary = db.get(LlmModel, model_id)
    if route and route.backup_model_id and primary and primary.status in {"disabled", "abnormal"}:
        backup = db.get(LlmModel, route.backup_model_id)
        if backup and backup.status == "enabled":
            selected_model_id = backup.id
            route_hit = ModelPolicyHit(
                id=new_id("mph"),
                model_id=selected_model_id,
                policy_id=route.id,
                hit_type="route_fallback",
                detail={"fromModelId": model_id, "toModelId": selected_model_id, "reason": f"primary_{primary.status}"},
            )
            db.add(route_hit)
    model_id = selected_model_id
    tokens = int(payload.get("tokens", 0))
    scope_candidates = [
        ("agent", payload.get("agentId")),
        ("department", payload.get("departmentId")),
        ("user", payload.get("userId")),
        ("model", model_id),
    ]
    quota = _find_quota(db, model_id, scope_candidates)
    route_overload = (route.fallback_policy or {}).get("overloadStrategy") if route else None
    overload = payload.get("overloadStrategy") or route_overload or "reject"
    current_qps = payload.get("currentQps")
    if quota and quota.qps_limit is not None and current_qps is not None and float(current_qps) > quota.qps_limit:
        return _handle_overload(db, payload, model_id, quota.id, "qps_limit", {"currentQps": current_qps, "limit": quota.qps_limit}, overload, route_hit)
    calls_today = payload.get("callsToday")
    if quota and quota.daily_call_limit is not None and calls_today is not None and int(calls_today) >= quota.daily_call_limit:
        return _handle_overload(db, payload, model_id, quota.id, "daily_call_limit", {"callsToday": calls_today, "limit": quota.daily_call_limit}, overload, route_hit)
    if quota and quota.daily_token_limit is not None and tokens > quota.daily_token_limit:
        hit = ModelPolicyHit(
            id=new_id("mph"),
            model_id=model_id,
            policy_id=quota.id,
            hit_type="daily_token_limit",
            detail={"tokens": tokens, "limit": quota.daily_token_limit, "decision": "reject"},
        )
        db.add(hit)
        return {"allowed": False, "policyHitId": hit.id, "reason": "daily_token_limit"}

    findings = content_policy_findings(payload.get("inputSummary"), payload.get("outputSummary"), payload.get("prompt"))
    if findings:
        hit = ModelPolicyHit(
            id=new_id("mph"),
            model_id=model_id,
            policy_id=None,
            hit_type="content_policy_violation",
            detail={"decision": "block", "findings": findings, "sanitizedInput": sanitize_summary(payload.get("inputSummary") or payload.get("prompt"), "masked input")},
        )
        db.add(hit)
        log = ModelCallLog(
            id=new_id("mcl"),
            user_id=payload.get("userId", "u001"),
            department_id=payload.get("departmentId"),
            project_id=payload.get("projectId"),
            agent_id=payload.get("agentId"),
            model_id=model_id,
            input_summary=sanitize_summary(payload.get("inputSummary") or payload.get("prompt"), "masked input"),
            output_summary=sanitize_summary(payload.get("outputSummary"), "blocked by content policy"),
            latency_ms=int(payload.get("latencyMs", 0)),
            tokens=tokens,
            cost=0,
            status="blocked",
            error_code="CONTENT_POLICY_VIOLATION",
        )
        db.add(log)
        alert = Alert(
            id=new_id("alt"),
            level="P1",
            status="pending",
            source_type="model_gateway",
            source_id=payload.get("agentId") or model_id,
            category="security",
            error_code="CONTENT_POLICY_VIOLATION",
            title="Model content policy violation",
            detail="Model input/output matched content compliance policy.",
            root_cause="Content moderation detected privacy, prompt injection, or non-compliant financial advice.",
            suggestion="Review the prompt and route to manual compliance review if needed.",
            owner_id=payload.get("userId"),
        )
        db.add(alert)
        return {"allowed": False, "policyHitId": hit.id, "modelCallLogId": log.id, "alertId": alert.id, "reason": "content_policy_violation", "findings": findings}

    model = db.get(LlmModel, model_id)
    cost = float(payload.get("cost", 0) or (tokens * (model.unit_price if model else 0)))
    log = ModelCallLog(
        id=new_id("mcl"),
        user_id=payload.get("userId", "u001"),
        department_id=payload.get("departmentId"),
        project_id=payload.get("projectId"),
        agent_id=payload.get("agentId"),
        model_id=model_id,
        input_summary=sanitize_summary(payload.get("inputSummary"), "masked input"),
        output_summary=sanitize_summary(payload.get("outputSummary"), "masked output"),
        latency_ms=int(payload.get("latencyMs", 0)),
        tokens=tokens,
        cost=cost,
        status="success",
    )
    db.add(log)
    hit = ModelPolicyHit(
        id=new_id("mph"),
        model_id=model_id,
        policy_id=route.id if route else (quota.id if quota else None),
        hit_type="route_selected",
        detail={"tokens": tokens, "decision": "allow", "requestedModelId": requested_model_id, "selectedModelId": model_id},
    )
    db.add(hit)
    return {"allowed": True, "modelCallLogId": log.id, "policyHitId": hit.id, "fallbackPolicyHitId": route_hit.id if route_hit else None, "modelId": model_id, "requestedModelId": requested_model_id, "cost": cost}


def _handle_overload(db: Session, payload: dict, model_id: str, policy_id: str | None, hit_type: str, detail: dict, strategy: str, route_hit: ModelPolicyHit | None) -> dict:
    strategy = strategy if strategy in {"queue", "reject", "degrade"} else "reject"
    hit = ModelPolicyHit(
        id=new_id("mph"),
        model_id=model_id,
        policy_id=policy_id,
        hit_type=hit_type,
        detail=detail | {"decision": strategy},
    )
    db.add(hit)
    if strategy == "reject":
        return {"allowed": False, "policyHitId": hit.id, "reason": hit_type, "decision": "reject"}
    log = ModelCallLog(
        id=new_id("mcl"),
        user_id=payload.get("userId", "u001"),
        department_id=payload.get("departmentId"),
        project_id=payload.get("projectId"),
        agent_id=payload.get("agentId"),
        model_id=model_id,
        input_summary=sanitize_summary(payload.get("inputSummary"), "masked input"),
        output_summary="queued by gateway" if strategy == "queue" else "degraded response by gateway",
        latency_ms=int(payload.get("latencyMs", 0)),
        tokens=int(payload.get("tokens", 0)),
        cost=0,
        status="queued" if strategy == "queue" else "degraded",
    )
    db.add(log)
    return {
        "allowed": True,
        "modelCallLogId": log.id,
        "policyHitId": hit.id,
        "fallbackPolicyHitId": route_hit.id if route_hit else None,
        "modelId": model_id,
        "requestedModelId": payload.get("modelId", "m001"),
        "decision": strategy,
        "queued": strategy == "queue",
        "degraded": strategy == "degrade",
        "cost": 0,
    }


def _find_route_policy(db: Session, requested_model_id: str, payload: dict) -> ModelRoutePolicy | None:
    scopes = [
        ("agent", payload.get("agentId")),
        ("department", payload.get("departmentId")),
        ("user", payload.get("userId")),
        ("model", requested_model_id),
    ]
    for scope_type, scope_id in scopes:
        if not scope_id:
            continue
        route = db.execute(
            select(ModelRoutePolicy).where(
                ModelRoutePolicy.scope_type == scope_type,
                (ModelRoutePolicy.primary_model_id == requested_model_id) | (ModelRoutePolicy.primary_model_id.is_(None)),
            )
        ).scalars().first()
        if route:
            return route
    return None


def _find_quota(db: Session, model_id: str, scopes: list[tuple[str, str | None]]) -> ModelQuotaPolicy | None:
    for scope_type, scope_id in scopes:
        if not scope_id:
            continue
        quota = db.execute(
            select(ModelQuotaPolicy).where(
                ModelQuotaPolicy.scope_type == scope_type,
                ModelQuotaPolicy.scope_id == scope_id,
                (ModelQuotaPolicy.model_id == model_id) | (ModelQuotaPolicy.model_id.is_(None)),
            )
        ).scalar_one_or_none()
        if quota:
            return quota
    return None
