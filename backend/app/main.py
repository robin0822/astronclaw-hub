from __future__ import annotations

import secrets

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.middleware.cors import CORSMiddleware

from app.api.v1.routes import router
from app.core.config import get_settings
from app.core.errors import BusinessError, INVALID_REQUEST
from app.core.responses import error_response


settings = get_settings()
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-Id") or f"req_{secrets.token_hex(12)}"
    response = await call_next(request)
    response.headers["X-Request-Id"] = request.state.request_id
    return response


@app.exception_handler(BusinessError)
async def business_error_handler(request: Request, exc: BusinessError):
    return error_response(request, exc.code, exc.message, exc.status_code, exc.data)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return error_response(request, INVALID_REQUEST, "invalid request", 422, {"errors": exc.errors()})


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(router, prefix=settings.api_prefix)
