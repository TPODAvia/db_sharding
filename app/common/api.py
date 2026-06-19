from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse, Response

from app.common.db import DatabasePool
from app.common.logging_config import configure_logging
from app.common.security import PROMETHEUS_CONTENT_TYPE, SecurityHeadersMiddleware, prometheus_metrics
from app.common.settings import settings


def error_payload(request: Request, *, code: str, message: object, details: object | None = None) -> dict[str, object]:
    error: dict[str, object] = {
        "code": code,
        "message": message,
        "request_id": getattr(request.state, "request_id", None),
    }
    if details is not None:
        error["details"] = details
    return {"error": error}


def create_app(title: str, db: DatabasePool) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging()
        await db.start()
        try:
            yield
        finally:
            await db.stop()

    app = FastAPI(title=title, lifespan=lifespan)
    app.add_middleware(SecurityHeadersMiddleware)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(request, code=str(exc.status_code), message=exc.detail),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_payload(
                request,
                code="VALIDATION_ERROR",
                message="Invalid request",
                details=exc.errors(),
            ),
        )

    @app.get("/metrics", include_in_schema=False)
    def metrics(request: Request) -> Response:
        if settings.metrics_auth_enabled:
            auth = request.headers.get("authorization", "")
            bearer = auth.split(" ", 1)[1].strip() if auth.lower().startswith("bearer ") else ""
            provided = request.headers.get("x-metrics-token") or bearer
            if not settings.metrics_token or not provided or provided != settings.metrics_token:
                return JSONResponse(
                    status_code=401,
                    content=error_payload(request, code="401", message="Metrics auth required"),
                )
        return Response(prometheus_metrics(), media_type=PROMETHEUS_CONTENT_TYPE)

    return app
