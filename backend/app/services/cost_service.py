from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Agent, CostDailyStat, Department, LlmModel, ModelCallLog, ResourcePackage


def archive_costs(db: Session, archive_date: date) -> dict[str, int]:
    start_at = datetime.combine(archive_date, time.min, tzinfo=timezone.utc)
    end_at = start_at + timedelta(days=1)
    logs = db.execute(
        select(ModelCallLog).where(
            ModelCallLog.status == "success",
            ModelCallLog.created_at >= start_at,
            ModelCallLog.created_at < end_at,
        )
    ).scalars().all()
    packages = db.execute(select(ResourcePackage).where(ResourcePackage.status == "active")).scalars().all()
    db.execute(delete(CostDailyStat).where(CostDailyStat.date == archive_date))

    stats: dict[tuple[str, str], dict] = {}
    matched_package_ids: set[str] = set()
    for log in logs:
        model = db.get(LlmModel, log.model_id) if log.model_id else None
        model_cost = log.cost if log.cost else (log.tokens or 0) * (model.unit_price if model else 0)
        dimensions = [
            ("department", log.department_id),
            ("project", log.project_id),
            ("model", log.model_id),
            ("agent", log.agent_id),
        ]
        for package in packages:
            if _package_matches_log(package, log):
                dimensions.append(("resource_package", package.id))
                matched_package_ids.add(package.id)
        for dimension_type, dimension_id in dimensions:
            if not dimension_id:
                continue
            key = (dimension_type, dimension_id)
            current = stats.setdefault(
                key,
                {
                    "dimension_type": dimension_type,
                    "dimension_id": dimension_id,
                    "dimension_name": _dimension_name(db, dimension_type, dimension_id),
                    "call_count": 0,
                    "tokens": 0,
                    "model_cost": 0.0,
                    "container_cost": 0.0,
                    "seat_cost": 0.0,
                },
            )
            current["call_count"] += 1
            current["tokens"] += log.tokens or 0
            if dimension_type == "resource_package":
                current["container_cost"] += model_cost
            else:
                current["model_cost"] += model_cost

    for package in packages:
        if package.id not in matched_package_ids and not package.fixed_daily_cost:
            continue
        key = ("resource_package", package.id)
        current = stats.setdefault(
            key,
            {
                "dimension_type": "resource_package",
                "dimension_id": package.id,
                "dimension_name": package.name,
                "call_count": 0,
                "tokens": 0,
                "model_cost": 0.0,
                "container_cost": 0.0,
                "seat_cost": 0.0,
            },
        )
        current["container_cost"] += package.fixed_daily_cost or 0

    for item in stats.values():
        total_cost = item["model_cost"] + item["container_cost"] + item["seat_cost"]
        db.add(CostDailyStat(date=archive_date, total_cost=total_cost, **item))

    return {"archivedStats": len(stats), "sourceLogs": len(logs)}


def _dimension_name(db: Session, dimension_type: str, dimension_id: str) -> str | None:
    if dimension_type == "department":
        department = db.get(Department, dimension_id)
        return department.name if department else dimension_id
    if dimension_type == "model":
        model = db.get(LlmModel, dimension_id)
        return model.name if model else dimension_id
    if dimension_type == "agent":
        agent = db.get(Agent, dimension_id)
        return agent.name if agent else dimension_id
    if dimension_type == "resource_package":
        package = db.get(ResourcePackage, dimension_id)
        return package.name if package else dimension_id
    return dimension_id


def _package_matches_log(package: ResourcePackage, log: ModelCallLog) -> bool:
    if package.target_type == "agent":
        return package.target_id == log.agent_id
    if package.target_type == "department":
        return package.target_id == log.department_id
    if package.target_type == "model":
        return package.target_id == log.model_id
    if package.target_type == "global":
        return True
    return False
