from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


def success(data: Any = None, request_id: str | None = None) -> dict[str, Any]:
    return {
        "code": 0,
        "message": "success",
        "data": data if data is not None else {},
        "requestId": request_id,
    }


def error_response(request: Request, code: int, message: str, status_code: int, data: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "message": message,
            "data": data if data is not None else {},
            "requestId": getattr(request.state, "request_id", None),
        },
    )
