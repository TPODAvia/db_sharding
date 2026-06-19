# TLS/mTLS layout

Run `./scripts/init_tls_certs.sh` for local development certificates.

Production should replace these files with certificates issued by the company CA, service mesh CA, ACME, or cloud load-balancer CA:

- `ca.crt` — trusted root/intermediate CA.
- `postgres_server.crt/key` — Citus/Postgres server certificate with SANs for coordinator/workers.
- `pgbouncer_server.crt/key` — PgBouncer server certificate for app clients.
- `pgbouncer_client.crt/key` — PgBouncer client certificate for Postgres server-side TLS.
- `app_client.crt/key` — application client certificate for app → PgBouncer mTLS.

The production app requires `DB_SSLMODE=verify-full` and `DB_SSL_CA_FILE`.
