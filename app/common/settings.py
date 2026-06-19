from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal

from app.common.env import get_env_or_file

TRUE_VALUES = {"1", "true", "yes", "on"}


def _env(name: str, default: str | None = None) -> str:
    value = get_env_or_file(name, default)
    if value is None or value == "":
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _int_env(name: str, default: int, *, min_value: int | None = None, max_value: int | None = None) -> int:
    raw = _env(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer, got {raw!r}") from exc
    if min_value is not None and value < min_value:
        raise RuntimeError(f"{name} must be >= {min_value}, got {value}")
    if max_value is not None and value > max_value:
        raise RuntimeError(f"{name} must be <= {max_value}, got {value}")
    return value


def _float_env(name: str, default: float, *, min_value: float | None = None) -> float:
    raw = _env(name, str(default))
    try:
        value = float(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a number, got {raw!r}") from exc
    if min_value is not None and value < min_value:
        raise RuntimeError(f"{name} must be >= {min_value}, got {value}")
    return value


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    service_name: str = os.getenv("SERVICE_NAME", "orders-service")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    pg_user: str = _env("PGUSER")
    pg_password: str = _env("PGPASSWORD")
    pg_database: str = _env("PGDATABASE", os.getenv("POSTGRES_DB", "gr5"))
    pgbouncer_host: str = _env("PGBOUNCER_HOST", "localhost")
    pgbouncer_port: int = _int_env("PGBOUNCER_PORT", 6432, min_value=1, max_value=65535)
    db_sslmode: str = os.getenv("DB_SSLMODE", "disable")  # disable | prefer | require | verify-ca | verify-full
    db_ssl_ca_file: str | None = os.getenv("DB_SSL_CA_FILE")
    db_ssl_cert_file: str | None = os.getenv("DB_SSL_CERT_FILE")
    db_ssl_key_file: str | None = os.getenv("DB_SSL_KEY_FILE")

    citus_worker_count: int = _int_env("CITUS_WORKER_COUNT", 2, min_value=1, max_value=1024)
    citus_shard_count: int = _int_env("CITUS_SHARD_COUNT", 32, min_value=1, max_value=4096)

    db_pool_min_size: int = _int_env("DB_POOL_MIN_SIZE", 1, min_value=0)
    db_pool_max_size: int = _int_env("DB_POOL_MAX_SIZE", 10, min_value=1)
    db_connect_retries: int = _int_env("DB_CONNECT_RETRIES", 30, min_value=1)
    db_connect_retry_delay_seconds: float = _float_env("DB_CONNECT_RETRY_DELAY_SECONDS", 1.0, min_value=0.1)
    db_command_timeout_seconds: float = _float_env("DB_COMMAND_TIMEOUT_SECONDS", 10.0, min_value=0.1)
    db_statement_timeout_ms: int = _int_env("DB_STATEMENT_TIMEOUT_MS", 5000, min_value=100)
    db_idle_transaction_timeout_ms: int = _int_env("DB_IDLE_TRANSACTION_TIMEOUT_MS", 10000, min_value=100)

    max_order_amount: Decimal = Decimal(os.getenv("MAX_ORDER_AMOUNT", "1000000.00"))
    max_payload_bytes: int = _int_env("MAX_PAYLOAD_BYTES", 8192, min_value=2)
    default_list_limit: int = _int_env("DEFAULT_LIST_LIMIT", 50, min_value=1)
    max_list_limit: int = _int_env("MAX_LIST_LIMIT", 500, min_value=1)

    api_key_read: str | None = get_env_or_file("APP_API_KEY_READ")
    api_key_write: str | None = get_env_or_file("APP_API_KEY_WRITE")
    api_key_admin: str | None = get_env_or_file("APP_API_KEY_ADMIN")
    # Backward-compatible single key; only for local/demo, not production.
    api_key: str | None = get_env_or_file("APP_API_KEY")
    require_api_key: bool = os.getenv("REQUIRE_API_KEY", "false").lower() in TRUE_VALUES
    auth_mode: str = os.getenv("AUTH_MODE", "api_key")  # disabled | api_key | jwt | api_key_or_jwt
    jwt_secret: str | None = get_env_or_file("JWT_SECRET")
    jwt_issuer: str = os.getenv("JWT_ISSUER", "orders-demo")
    jwt_audience: str = os.getenv("JWT_AUDIENCE", "orders-api")

    enforce_tenant_auth: bool = os.getenv("ENFORCE_TENANT_AUTH", "true").lower() in TRUE_VALUES
    rate_limit_enabled: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in TRUE_VALUES
    rate_limit_backend: str = os.getenv("RATE_LIMIT_BACKEND", "redis")  # redis | memory | gateway
    redis_url: str | None = os.getenv("REDIS_URL")
    rate_limit_requests: int = _int_env("RATE_LIMIT_REQUESTS", 300, min_value=1)
    rate_limit_window_seconds: int = _int_env("RATE_LIMIT_WINDOW_SECONDS", 60, min_value=1)
    idempotency_retention_days: int = _int_env("IDEMPOTENCY_RETENTION_DAYS", 7, min_value=1)

    metrics_auth_enabled: bool = os.getenv("METRICS_AUTH_ENABLED", "false").lower() in TRUE_VALUES
    metrics_token: str | None = get_env_or_file("METRICS_TOKEN")

    migration_db_host: str = os.getenv("MIGRATION_DB_HOST", "citus_coordinator")
    migration_db_port: int = _int_env("MIGRATION_DB_PORT", 5432, min_value=1, max_value=65535)

    def validate(self) -> None:
        if self.db_pool_min_size > self.db_pool_max_size:
            raise RuntimeError("DB_POOL_MIN_SIZE cannot be greater than DB_POOL_MAX_SIZE")
        if self.auth_mode not in {"disabled", "api_key", "jwt", "api_key_or_jwt"}:
            raise RuntimeError("AUTH_MODE must be one of: disabled, api_key, jwt, api_key_or_jwt")
        if self.require_api_key and not any([self.api_key_read, self.api_key_write, self.api_key_admin, self.api_key]):
            raise RuntimeError("REQUIRE_API_KEY=true requires at least one API key")
        if self.rate_limit_backend not in {"redis", "memory", "gateway"}:
            raise RuntimeError("RATE_LIMIT_BACKEND must be one of: redis, memory, gateway")
        if self.db_sslmode not in {"disable", "prefer", "require", "verify-ca", "verify-full"}:
            raise RuntimeError("DB_SSLMODE must be one of: disable, prefer, require, verify-ca, verify-full")
        if self.auth_mode in {"jwt", "api_key_or_jwt"} and not self.jwt_secret:
            raise RuntimeError("JWT_SECRET is required when JWT auth is enabled")
        if self.app_env == "production":
            if self.pg_password in {"admin", "password", "postgres", "gr5"}:
                raise RuntimeError("Refusing to start in production with an insecure database password")
            if self.db_sslmode != "verify-full":
                raise RuntimeError("DB_SSLMODE=verify-full is required in production")
            if not self.db_ssl_ca_file:
                raise RuntimeError("DB_SSL_CA_FILE is required in production")
            if self.auth_mode == "disabled":
                raise RuntimeError("AUTH_MODE=disabled is not allowed in production")
            if self.auth_mode in {"api_key", "api_key_or_jwt"} and not all(
                [self.api_key_read, self.api_key_write, self.api_key_admin]
            ):
                raise RuntimeError("APP_API_KEY_READ/WRITE/ADMIN are required in production for API key auth")
            if self.api_key:
                raise RuntimeError("APP_API_KEY single super-key is not allowed in production; use split API keys")
            if self.auth_mode in {"jwt", "api_key_or_jwt"} and not self.jwt_secret:
                raise RuntimeError("JWT_SECRET is required in production for JWT auth")
            if self.rate_limit_enabled and self.rate_limit_backend == "redis" and not self.redis_url:
                raise RuntimeError("REDIS_URL is required in production for Redis-backed rate limiting")
            if self.rate_limit_enabled and self.rate_limit_backend == "memory":
                raise RuntimeError("RATE_LIMIT_BACKEND=memory is not allowed in production")
            if not self.metrics_auth_enabled:
                raise RuntimeError("METRICS_AUTH_ENABLED=true is required in production")
            if self.metrics_auth_enabled and not self.metrics_token:
                raise RuntimeError("METRICS_TOKEN is required when METRICS_AUTH_ENABLED=true")


settings = Settings()
settings.validate()
