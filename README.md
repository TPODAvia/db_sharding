# Production-grade Orders Platform: FastAPI + PgBouncer + Citus + UUIDv7

This project is a production-oriented backend example for an orders service. It uses:

- **FastAPI** for writer/reader services;
- **UUIDv7** for time-sortable globally unique IDs;
- **Citus** instead of custom application sharding;
- **PgBouncer** for OLTP connection pooling;
- **Alembic** for schema migrations;
- **JWT / split API keys** for authentication;
- **tenant authorization** through JWT `tenant_id`;
- **idempotency keys** for safe order creation retries;
- **Prometheus metrics**, structured JSON logs, and alert rules;
- **Nginx TLS/mTLS gateway**;
- **Docker secrets pattern** and local secret generation;
- **pgBackRest/PITR templates** for production backup design.

The application connects only to the **Citus coordinator**. It does not know physical shards and does not connect to Citus workers directly.

```text
client
  |
  | HTTPS/mTLS
  v
Nginx gateway
  |
  +--> writer_service / reader_service
           |
           v
        PgBouncer
           |
           v
    Citus coordinator
           |
           +--> citus_worker1
           +--> citus_worker2
           +--> citus_workerN
```

## Why UUIDv7 instead of Snowflake

Snowflake requires globally unique worker IDs. In production that means extra coordination through Kubernetes ordinals, Consul, etcd, ZooKeeper, or a custom allocator. UUIDv7 avoids this operational risk while still being time-sortable.

The project generates UUIDv7 in Python because the Compose stack targets Citus on PostgreSQL 16. PostgreSQL 18+ can replace the wrapper with native `uuidv7()`.

## Why Citus instead of custom sharding

Custom sharding forces the application to own routing, rebalancing, migrations per shard, and cross-shard behavior. Citus moves this responsibility into the database layer. The distributed table is:

```sql
orders distributed by user_id
```

Hot-path queries always include `user_id`, allowing Citus to route them efficiently.

## Quick start

```bash
cp .env.example .env
./scripts/init_citus_cluster.sh 2
```

This single command:

1. creates local secret files if missing;
2. renders Citus worker Compose config;
3. starts coordinator and workers;
4. registers workers in Citus metadata;
5. applies Alembic migrations through direct coordinator connection;
6. validates distributed tables and shard count;
7. starts PgBouncer, writer, and reader services.

Check services:

```bash
curl http://localhost:8001/health
curl http://localhost:8001/ready
curl http://localhost:8002/metrics
```

## Authentication

Production should use JWT/OIDC. Local/demo can use admin API key.

Generate a JWT for tenant/user `42`:

```bash
JWT_SECRET_FILE=docker/secrets/jwt_secret.txt \
python scripts/create_jwt.py \
  --sub user-42 \
  --tenant-id 42 \
  --roles orders:read,orders:write
```

Generate an admin JWT:

```bash
JWT_SECRET_FILE=docker/secrets/jwt_secret.txt \
python scripts/create_jwt.py \
  --sub admin \
  --roles admin,orders:read,orders:write
```

API keys are split by privilege:

- `APP_API_KEY_READ`
- `APP_API_KEY_WRITE`
- `APP_API_KEY_ADMIN`

The old single `APP_API_KEY` is accepted only outside production and refused in `APP_ENV=production`.

## Tenant authorization

When `ENFORCE_TENANT_AUTH=true`, non-admin JWT clients can only access their own `user_id`:

```text
JWT tenant_id=42 -> can access /api/v1/users/42/orders
JWT tenant_id=42 -> cannot access /api/v1/users/100/orders
```

Admin principals can access all tenants.

## API examples

Create an order safely with idempotency:

```bash
TOKEN="..."
IDEMPOTENCY_KEY="order-create-$(date +%s)-$RANDOM"

curl -X POST http://localhost:8001/api/v1/orders \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $IDEMPOTENCY_KEY" \
  -d '{"user_id":42,"amount":123.45,"status":"pending","payload":{"source":"demo"}}'
```

List orders for a user:

```bash
curl http://localhost:8002/api/v1/users/42/orders \
  -H "Authorization: Bearer $TOKEN"
```

Get one order by scalable Citus path:

```bash
curl http://localhost:8002/api/v1/users/42/orders/<uuidv7> \
  -H "Authorization: Bearer $TOKEN"
```

Admin-only fan-out endpoints:

```bash
curl http://localhost:8001/api/v1/admin/orders/<uuidv7> \
  -H "Authorization: Bearer $ADMIN_TOKEN"

curl http://localhost:8002/api/v1/admin/orders/pending \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

## Adding a Citus worker

Add a new worker and rebalance existing shards:

```bash
./scripts/add_citus_worker.sh 3
```

The script:

1. updates `CITUS_WORKER_COUNT` in `.env`;
2. renders `docker-compose.workers.yml`;
3. starts the new worker;
4. registers it in Citus coordinator metadata;
5. applies migrations through direct coordinator connection;
6. runs `rebalance_table_shards('orders')`;
7. restarts app services.

## Migrations

Do not run Citus DDL through PgBouncer transaction pooling.

Use:

```bash
./scripts/migrate_db_direct.sh
```

This connects directly to `citus_coordinator:5432`.

Important: `CITUS_SHARD_COUNT` is used when a distributed table is first created. Changing it later does not automatically repartition existing distributed tables. Repartitioning requires a separate operational plan.

## Secrets

The repository ships only `.example` secret files. Generate local secrets:

```bash
./scripts/init_secrets.sh
```

Production should use a real secret manager such as Kubernetes Secrets + External Secrets, HashiCorp Vault, AWS Secrets Manager, GCP Secret Manager, or Azure Key Vault.

## Monitoring and alerts

Prometheus config:

```text
infra/prometheus/prometheus.yml
infra/prometheus/alerts.yml
```

Run monitoring profile:

```bash
docker compose -f docker-compose.yml -f docker-compose.workers.yml --profile monitoring up -d
```

Application metrics include:

- total HTTP requests;
- 5xx count;
- status-code counters;
- auth failures;
- forbidden auth decisions;
- rate-limited requests;
- idempotency replays;
- request latency histogram.

## Logging

Application logs are structured JSON and include:

- timestamp;
- level;
- service name;
- request id;
- method/path/status;
- duration;
- principal when available.

## Backup and restore

Small/demo logical backups are still available:

```bash
./scripts/backup_all_shards.sh
./scripts/restore_citus_backup.sh <dump_file>
```

Real production should use PITR with pgBackRest or Barman. Templates were added:

```text
infra/backup/pgbackrest.conf.example
scripts/backup_full.sh
scripts/restore_pitr.sh
scripts/verify_backup.sh
```

Before production launch, verify restore in staging.

## TLS/mTLS gateway

The Nginx gateway profile requires client certificates:

```nginx
ssl_verify_client on;
```

Run:

```bash
docker compose -f docker-compose.yml -f docker-compose.workers.yml --profile gateway up -d
```

Certificates are expected under:

```text
infra/nginx/certs/
```

## CI and quality

CI performs:

- Python compile check;
- Ruff lint;
- Bandit security scan;
- pytest unit tests;
- Docker Compose config validation;
- non-blocking `pip-audit`.

Pre-commit config is included:

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

## Production caveats

Docker Compose is suitable for local development and production-like staging. Real production should use an orchestrator and managed operational controls:

- Kubernetes/Nomad/systemd or managed containers;
- real secret manager;
- PITR backups with restore drills;
- Alertmanager routing;
- OpenTelemetry tracing;
- network policies/firewalls blocking direct access to workers;
- separated DB roles for app, migration, monitoring, backup;
- image scanning and signed images;
- resource requests/limits.

See:

- `PRODUCTION_CHECKLIST.md`
- `docs/production-deployment.md`
- `deploy/k8s/README.md`

---

# P0/P1 production hardening notes

This revision applies the P0/P1 hardening pass from the audit.

## Important operational changes

### Bootstrap

Use one command for a fresh local/staging cluster:

```bash
cp .env.example .env
./scripts/init_citus_cluster.sh 2
```

The bootstrap script now:

1. loads `.env` for shell variables;
2. generates local secret files if missing;
3. starts coordinator and workers;
4. creates dedicated DB roles on coordinator/workers;
5. registers Citus workers;
6. applies Alembic migrations directly to the coordinator;
7. starts PgBouncer and app services.

### Dedicated DB users

The app no longer needs to run as the bootstrap `POSTGRES_USER`.

Configured roles:

- `APP_DB_USER` — app runtime role;
- `MIGRATION_DB_USER` — Alembic/Citus DDL role;
- `READONLY_DB_USER` — read-only access;
- `MONITORING_DB_USER` — postgres exporter / `pg_monitor`;
- `BACKUP_DB_USER` — backup/replication role.

Secrets are generated by:

```bash
./scripts/init_secrets.sh
```

### Idempotency

`POST /api/v1/orders` supports `Idempotency-Key`. The key is safe now:

- same key + same body = stored response replay;
- same key + different body = `409 Conflict`.

### Metrics

Production must protect metrics:

```env
METRICS_AUTH_ENABLED=true
METRICS_TOKEN_FILE=/run/secrets/metrics_token
```

Prometheus is configured to read the token from Docker secret and use it as a bearer token.

### Rate limiting

Production must use Redis or gateway-based rate limiting:

```env
RATE_LIMIT_ENABLED=true
RATE_LIMIT_BACKEND=redis
REDIS_URL=redis://redis:6379/0
```

`RATE_LIMIT_BACKEND=memory` is allowed only for local tests and is rejected in production.

### Adding Citus workers

Add/register a new worker:

```bash
./scripts/add_citus_worker.sh 3
```

Existing shards are **not automatically rebalanced** by default. Check placement first:

```bash
./scripts/rebalance_citus.sh --dry-run
```

Then execute during a maintenance window:

```bash
./scripts/rebalance_citus.sh --execute
```

To keep the previous one-command behavior for staging/demo:

```bash
REBALANCE_AFTER_ADD=true ./scripts/add_citus_worker.sh 3
```

## Production hardening added

This refactor focuses on four production-critical areas:

1. **TLS/mTLS**
   - external Nginx gateway mTLS;
   - internal app → PgBouncer TLS with client certificates;
   - PgBouncer → Citus/Postgres TLS with certificate verification;
   - local certificate generator: `./scripts/init_tls_certs.sh`;
   - production startup validation requires `DB_SSLMODE=verify-full`.

2. **Backup/restore**
   - logical Citus backup with manifest and checksums: `./scripts/backup_all_shards.sh`;
   - integrity verification: `./scripts/verify_backup.sh <backup_dir>`;
   - restore drill into a temporary database: `./scripts/backup_restore_drill.sh <backup_dir>`;
   - protected production restore: `RESTORE_CONFIRM=I_UNDERSTAND_THIS_REPLACES_DATA ./scripts/restore_citus_backup.sh <backup_dir>`.

3. **CI/CD**
   - lint, format, tests, Bandit, pip-audit;
   - compose validation;
   - image build validation;
   - Trivy filesystem and image scanning;
   - Citus integration smoke test and logical backup verification.

4. **Runtime hardening**
   - read-only root filesystem where possible;
   - tmpfs writable paths;
   - `no-new-privileges`;
   - dropped Linux capabilities;
   - pids, CPU and memory limits;
   - local-only port exposure for internal services.

Runbooks:

- `docs/runbooks/tls-mtls.md`
- `docs/runbooks/backup-restore.md`
- `docs/runbooks/runtime-hardening.md`
