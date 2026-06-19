# TLS/mTLS runbook

## Local development

```bash
./scripts/init_tls_certs.sh
./scripts/init_secrets.sh
./scripts/init_citus_cluster.sh 2
```

This generates a local CA and service certificates for:

- external gateway mTLS: client -> Nginx gateway;
- internal DB mTLS: application -> PgBouncer;
- encrypted/verified server TLS: PgBouncer -> Citus/Postgres.

## Production requirements

Use certificates from a trusted CA, service mesh, or cloud PKI. Do not use generated local keys.

Required production values:

```env
APP_ENV=production
DB_SSLMODE=verify-full
DB_SSL_CA_FILE=/run/tls/ca.crt
DB_SSL_CERT_FILE=/run/tls/app_client.crt
DB_SSL_KEY_FILE=/run/tls/app_client.key
PGBOUNCER_CLIENT_TLS_SSLMODE=verify-ca
PGBOUNCER_SERVER_TLS_SSLMODE=verify-full
POSTGRES_SSL=on
```

## Verification

```bash
openssl x509 -in infra/tls/certs/pgbouncer_server.crt -noout -issuer -subject -dates -ext subjectAltName
docker compose exec pgbouncer pgbouncer -R /etc/pgbouncer/pgbouncer.ini
```

App startup refuses `APP_ENV=production` unless `DB_SSLMODE=verify-full` and a CA file are configured.
