from __future__ import annotations

from sqlalchemy.orm import Session

from app.id_gen import new_id
from app.models import KnowledgeFile, KnowledgeParseTask


ALLOWED_FILE_TYPES = {"pdf", "docx", "txt", "xlsx", "pptx", "md"}
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024
SENSITIVE_MARKERS = ("api_key", "api-secret", "api_secret", "password=", "token=", "id_card=", "bank_card=")


def create_parse_task(db: Session, file: KnowledgeFile, phase: str = "validating") -> KnowledgeParseTask:
    task = KnowledgeParseTask(id=new_id("kpt"), file_id=file.id, status="queued", phase=phase)
    db.add(task)
    return task


def validate_file_type(file_type: str) -> bool:
    return file_type.lower() in ALLOWED_FILE_TYPES


def validate_file_security(payload: dict) -> tuple[bool, str | None]:
    file_type = str(payload.get("fileType", "txt")).lower()
    size_bytes = int(payload.get("sizeBytes", 0) or 0)
    sample = str(payload.get("contentPreview") or payload.get("sampleContent") or "")
    force_virus = bool(payload.get("virusDetected") or payload.get("mockVirusDetected"))
    if not validate_file_type(file_type):
        return False, "unsupported file type"
    if size_bytes <= 0:
        return False, "file size must be positive"
    if size_bytes > MAX_FILE_SIZE_BYTES:
        return False, "file size exceeds 50MB limit"
    if force_virus or "eicar" in sample.lower():
        return False, "virus scan failed"
    sample_lower = sample.lower()
    if any(marker in sample_lower for marker in SENSITIVE_MARKERS):
        return False, "sensitive content detected"
    return True, None


def process_parse_task_if_mock(file: KnowledgeFile, task: KnowledgeParseTask | None) -> None:
    if not task or task.status not in {"queued", "running"}:
        return
    if file.status == "failed":
        task.status = "failed"
        task.phase = task.phase or "validating"
        task.error_message = file.parse_error or "file validation failed"
        return
    if not validate_file_type(file.file_type):
        task.status = "failed"
        task.phase = "validating"
        task.error_message = "unsupported file type"
        file.status = "failed"
        file.parse_error = task.error_message
        return
    task.status = "success"
    task.phase = "indexed"
    file.status = "indexed"
    file.parse_error = None
