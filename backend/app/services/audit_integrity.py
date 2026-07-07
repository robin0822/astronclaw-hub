from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def audit_timestamp(value: datetime) -> str:
    if value.tzinfo is not None:
        value = value.replace(tzinfo=None)
    return value.isoformat()


def audit_hash_payload(
    *,
    hash_prev: str,
    actor_id: str | None,
    module: str,
    action: str,
    object_type: str,
    object_id: str | None,
    result: str,
    error_message: str | None,
    before_value: dict[str, Any] | None,
    after_value: dict[str, Any] | None,
    created_at: datetime,
) -> str:
    payload = {
        "hashPrev": hash_prev or "",
        "actorId": actor_id,
        "module": module,
        "action": action,
        "objectType": object_type,
        "objectId": object_id,
        "result": result,
        "errorMessage": error_message,
        "beforeValue": before_value,
        "afterValue": after_value,
        "createdAt": audit_timestamp(created_at),
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
