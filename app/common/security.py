from __future__ import annotations

import json
import logging
import secrets
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import jwt
from fastapi import HTTPException, Request, status
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from redis.asyncio import Redis
from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.common.settings import settings

PUBLIC_PATHS = {"/health", "/ready"}
logger = logging.getLogger(__name__)

HTTP_REQUESTS = Counter("app_http_requests_total", "Total HTTP requests")
HTTP_5XX = Counter("app_http_5xx_total", "Total 5xx responses")
HTTP_STATUS = Counter("app_http_status_total", "HTTP responses by status", ["status"])
AUTH_FAILURES = Counter("app_auth_failures_total", "Authentication failures")
AUTH_FORBIDDEN = Counter("app_auth_forbidden_total", "Authorization failures")
RATE_LIMITED = Counter("app_rate_limited_total", "Rate-limited requests")
IDEMPOTENCY_REPLAYS = Counter("app_idempotency_replays_total", "Idempotency replay responses")
IDEMPOTENCY_CONFLICTS = Counter("app_idempotency_conflicts_total", "Idempotency key conflicts")
DB_ERRORS = Counter("app_db_errors_total", "Database operation failures")
REQUEST_LATENCY = Histogram(
    "app_http_request_duration_seconds",
    "HTTP request duration in seconds",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)
CITUS_ACTIVE_WORKERS = Gauge("app_citus_active_workers", "Active Citus worker nodes")
CITUS_SHARD_COUNT = Gauge("app_citus_shard_count", "Total Citus shards")

_COUNTERS = {
    "http_requests_total": HTTP_REQUESTS,
    "http_5xx_total": HTTP_5XX,
    "auth_failures_total": AUTH_FAILURES,
    "auth_forbidden_total": AUTH_FORBIDDEN,
    "rate_limited_total": RATE_LIMITED,
    "idempotency_replays_total": IDEMPOTENCY_REPLAYS,
    "idempotency_conflicts_total": IDEMPOTENCY_CONFLICTS,
    "db_errors_total": DB_ERRORS,
}
_GAUGES = {
    "citus_active_workers": CITUS_ACTIVE_WORKERS,
    "citus_shard_count": CITUS_SHARD_COUNT,
}
_RATE_WINDOWS: dict[str, deque[float]] = defaultdict(deque)
_REDIS: Redis | None = None


@dataclass(frozen=True)
class Principal:
    subject: str
    roles: set[str]
    tenant_id: int | None = None
    auth_method: str = "unknown"

    @property
    def is_admin(self) -> bool:
        return "admin" in self.roles


def sign_jwt(payload: dict[str, Any], secret: str) -> str:
    headers = {"typ": "JWT", "alg": "HS256"}
    return jwt.encode(payload, secret, algorithm="HS256", headers=headers)


def verify_jwt(token: str) -> Principal:
    if not settings.jwt_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="JWT auth is not configured")
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid JWT") from exc

    roles_raw = payload.get("roles", [])
    roles = set(roles_raw if isinstance(roles_raw, list) else [])
    tenant_raw = payload.get("tenant_id") or payload.get("user_id")
    tenant_id: int | None = None
    if tenant_raw is not None:
        try:
            tenant_id = int(tenant_raw)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid tenant_id claim") from exc
    return Principal(subject=str(payload["sub"]), roles=roles, tenant_id=tenant_id, auth_method="jwt")


def _api_key_principal(request: Request) -> Principal | None:
    provided = request.headers.get("x-api-key")
    if not provided:
        return None
    # Split API keys are intended for internal service-to-service/admin use. Tenant-scoped public access should use JWT.
    key_roles = [
        (settings.api_key_read, {"orders:read", "internal"}, "api-key-read"),
        (settings.api_key_write, {"orders:read", "orders:write", "internal"}, "api-key-write"),
        (settings.api_key_admin, {"orders:read", "orders:write", "admin", "internal"}, "api-key-admin"),
    ]
    if settings.api_key and settings.app_env != "production":
        key_roles.append((settings.api_key, {"orders:read", "orders:write", "admin", "internal"}, "api-key-legacy"))
    for expected, roles, method in key_roles:
        if expected and secrets.compare_digest(provided, expected):
            return Principal(subject=method, roles=roles, auth_method=method)
    return None


def _bearer_principal(request: Request) -> Principal | None:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    return verify_jwt(auth.split(" ", 1)[1].strip())


def _rate_limit_key(request: Request) -> str:
    principal = getattr(request.state, "principal", None)
    if isinstance(principal, Principal):
        return f"principal:{principal.subject}"
    client = request.client.host if request.client else "unknown"
    return f"ip:{client}"


def _redis() -> Redis:
    global _REDIS
    if _REDIS is None:
        if not settings.redis_url:
            raise RuntimeError("REDIS_URL is not configured")
        _REDIS = Redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    return _REDIS


async def _enforce_memory_rate_limit(request: Request) -> None:
    now = time.monotonic()
    window = settings.rate_limit_window_seconds
    bucket = _RATE_WINDOWS[_rate_limit_key(request)]
    while bucket and bucket[0] <= now - window:
        bucket.popleft()
    if len(bucket) >= settings.rate_limit_requests:
        RATE_LIMITED.inc()
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")
    bucket.append(now)


async def _enforce_redis_rate_limit(request: Request) -> None:
    window = settings.rate_limit_window_seconds
    bucket = int(time.time() // window)
    key = f"rate-limit:{_rate_limit_key(request)}:{bucket}"
    try:
        count = await _redis().incr(key)
        if count == 1:
            await _redis().expire(key, window + 5)
    except RedisError as exc:
        logger.exception("redis_rate_limit_failed")
        if settings.app_env == "production":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Rate limiter unavailable",
            ) from exc
        await _enforce_memory_rate_limit(request)
        return
    if int(count) > settings.rate_limit_requests:
        RATE_LIMITED.inc()
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")


async def _enforce_rate_limit(request: Request) -> None:
    if not settings.rate_limit_enabled or request.url.path in PUBLIC_PATHS:
        return
    if settings.rate_limit_backend == "gateway":
        return
    if settings.rate_limit_backend == "redis":
        await _enforce_redis_rate_limit(request)
    else:
        await _enforce_memory_rate_limit(request)


async def require_api_key(request: Request) -> None:
    await require_role("orders:read")(request)


def require_role(role: str) -> Callable[[Request], Awaitable[None]]:
    async def dependency(request: Request) -> None:
        if request.url.path in PUBLIC_PATHS:
            return
        if settings.auth_mode == "disabled" and settings.app_env != "production":
            return

        principal: Principal | None = None
        if settings.auth_mode in {"api_key", "api_key_or_jwt"}:
            principal = _api_key_principal(request)
        if principal is None and settings.auth_mode in {"jwt", "api_key_or_jwt"}:
            principal = _bearer_principal(request)

        if principal is None:
            AUTH_FAILURES.inc()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        if role not in principal.roles and "admin" not in principal.roles:
            AUTH_FORBIDDEN.inc()
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing required role")
        request.state.principal = principal
        await _enforce_rate_limit(request)

    return dependency


def require_tenant_access(request: Request, user_id: int) -> None:
    if not settings.enforce_tenant_auth:
        return
    principal = getattr(request.state, "principal", None)
    if not isinstance(principal, Principal):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    if principal.is_admin or "internal" in principal.roles:
        return
    if principal.tenant_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="tenant_id claim is required")
    if principal.tenant_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant access denied")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()
        HTTP_REQUESTS.inc()
        try:
            response = await call_next(request)
        except Exception:
            HTTP_5XX.inc()
            logger.exception(
                "unhandled_request_error",
                extra={"request_id": request_id, "method": request.method, "path": request.url.path},
            )
            raise
        duration = time.perf_counter() - started
        REQUEST_LATENCY.observe(duration)
        status_code = response.status_code
        HTTP_STATUS.labels(status=str(status_code)).inc()
        if status_code >= 500:
            HTTP_5XX.inc()
        logger.info(
            "request_finished",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": round(duration * 1000, 2),
                "principal": getattr(getattr(request.state, "principal", None), "subject", None),
            },
        )
        response.headers["x-request-id"] = request_id
        response.headers["x-content-type-options"] = "nosniff"
        response.headers["x-frame-options"] = "DENY"
        response.headers["referrer-policy"] = "no-referrer"
        response.headers["permissions-policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["strict-transport-security"] = "max-age=31536000; includeSubDomains"
        response.headers["server-timing"] = f"app;dur={duration * 1000:.2f}"
        return response


def payload_size_bytes(payload: dict[str, Any]) -> int:
    return len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def inc_metric(name: str, value: float = 1) -> None:
    metric = _COUNTERS.get(name)
    if metric is not None:
        metric.inc(value)
        return
    gauge = _GAUGES.get(name)
    if gauge is not None:
        gauge.set(value)


def prometheus_metrics() -> bytes:
    return generate_latest()


PROMETHEUS_CONTENT_TYPE = CONTENT_TYPE_LATEST
