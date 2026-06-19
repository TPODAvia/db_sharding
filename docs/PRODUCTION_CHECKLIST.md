# Production checklist

This revision closes the main production gaps found in the previous Citus/UUIDv7 version.

## Startup and Citus

- [x] Use `scripts/init_citus_cluster.sh <worker_count>` as the single cluster bootstrap command.
- [x] Register all Citus workers with the coordinator before Alembic migrations.
- [x] Verify active workers, distributed tables, and shard count after bootstrap.
- [x] Run Alembic/Citus DDL through direct coordinator connection, not PgBouncer transaction pooling.
- [x] Use `scripts/add_citus_worker.sh <new_total_worker_count>` for one-command worker add + rebalance.

## Security

- [x] No real secret `.txt` files are shipped; only `.example` templates are included.
- [x] `scripts/init_secrets.sh` creates local secret files with restrictive permissions.
- [x] Split API keys by privilege: read, write, admin.
- [x] Single legacy `APP_API_KEY` is refused in production.
- [x] JWT validation uses PyJWT with issuer/audience/expiration validation.
- [x] Tenant authorization requires JWT `tenant_id`/`user_id` claim unless principal is admin.
- [x] Gateway mTLS is set to `ssl_verify_client on`.
- [x] Nginx request limiting is enabled at the gateway.

## API safety

- [x] Public API is versioned under `/api/v1`.
- [x] `POST /api/v1/orders` supports `Idempotency-Key`.
- [x] Fan-out order lookup moved to admin-only endpoint `/api/v1/admin/orders/{order_id}`.
- [x] Fan-out pending order list moved to admin-only endpoint `/api/v1/admin/orders/pending`.
- [x] Standard JSON error envelope includes `request_id`.

## Observability

- [x] Structured JSON logs.
- [x] Request ID propagation.
- [x] Prometheus counters and latency histogram.
- [x] Alert rules skeleton.
- [x] Citus readiness exposes active workers and distributed shard count.

## Backup and restore

- [x] Existing logical dump scripts remain for demo/small data.
- [x] pgBackRest/PITR templates added for real production backup strategy.
- [ ] Configure WAL archive destination outside the Docker host.
- [ ] Run a restore drill in staging before production launch.

## CI and quality

- [x] Python compile check.
- [x] Pytest unit tests.
- [x] Ruff config and pre-commit config.
- [x] Bandit scan in CI.
- [x] pip-audit in CI as non-blocking supply-chain check.
- [ ] Add real Docker-based Citus integration test job if CI runner time/resources allow it.

## Deployment

- [x] Docker Compose production-like local/staging setup.
- [x] Kubernetes/Helm deployment notes added.
- [ ] Implement actual Helm/Kustomize manifests for the target environment.
- [ ] Add OpenTelemetry exporter and tracing backend.
- [ ] Add Alertmanager routing.

## P0/P1 hardening applied in this version

- `jsonb` values are serialized explicitly before being sent through `asyncpg`.
- `Idempotency-Key` now stores a stable SHA-256 request hash and returns `409 Conflict` if the same key is reused with a different body.
- Shell runbooks load `.env` via `scripts/lib_env.sh`; Docker Compose and bash now use the same values.
- Alembic uses `SQLAlchemy URL.create()` and connects directly to the Citus coordinator, not PgBouncer transaction pooling.
- Dedicated DB roles were added: `app_user`, `migration_user`, `readonly_user`, `monitoring_user`, `backup_user`.
- PgBouncer accepts the app and migration roles instead of only the bootstrap superuser.
- Redis-backed rate limiting was added. `RATE_LIMIT_BACKEND=memory` is rejected in production.
- `/metrics` can be protected by `METRICS_AUTH_ENABLED=true` and `METRICS_TOKEN`; production requires this.
- Metrics were moved to `prometheus-client` counters/gauges/histograms instead of hand-built global variables.
- Prometheus uses `bearer_token_file` for protected service metrics.
- pgBackRest templates now model coordinator + worker stanzas for Citus PITR.
- CI now has a Citus integration job skeleton that bootstraps the cluster and validates Citus metadata.
- Rebalancing is no longer an unsafe default when adding a worker. Use `scripts/rebalance_citus.sh --dry-run` and then `--execute` during a maintenance window.

## Still environment-dependent

The repository includes production runbooks and templates, but real production still requires infrastructure choices outside this ZIP:

- HA/failover for Citus coordinator and PgBouncer.
- A real secret manager such as Vault, cloud secret manager, SOPS, or Kubernetes Secrets encrypted at rest.
- Real TLS/mTLS certificate lifecycle: issuing, rotation, revocation, expiry alerts.
- Production object storage and credentials for pgBackRest.
- Kubernetes/Nomad/managed platform manifests with anti-affinity, resource requests/limits, rolling updates, and persistent volume policies.
