#!/usr/bin/env bash
set -euo pipefail

CERT_DIR="${TLS_CERT_DIR:-infra/tls/certs}"
DAYS="${TLS_CERT_DAYS:-825}"
mkdir -p "$CERT_DIR"

if ! command -v openssl >/dev/null 2>&1; then
  echo "openssl is required" >&2
  exit 1
fi

openssl genrsa -out "$CERT_DIR/ca.key" 4096
openssl req -x509 -new -nodes -key "$CERT_DIR/ca.key" -sha256 -days "$DAYS" \
  -subj "/CN=orders-demo-local-ca" -out "$CERT_DIR/ca.crt"

make_cert() {
  local name="$1"
  local cn="$2"
  local san="$3"
  openssl genrsa -out "$CERT_DIR/${name}.key" 2048
  cat > "$CERT_DIR/${name}.cnf" <<CFG
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
req_extensions = v3_req

[dn]
CN = ${cn}

[v3_req]
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth,clientAuth
subjectAltName = ${san}
CFG
  openssl req -new -key "$CERT_DIR/${name}.key" -out "$CERT_DIR/${name}.csr" -config "$CERT_DIR/${name}.cnf"
  openssl x509 -req -in "$CERT_DIR/${name}.csr" -CA "$CERT_DIR/ca.crt" -CAkey "$CERT_DIR/ca.key" \
    -CAcreateserial -out "$CERT_DIR/${name}.crt" -days "$DAYS" -sha256 \
    -extensions v3_req -extfile "$CERT_DIR/${name}.cnf"
  rm -f "$CERT_DIR/${name}.csr" "$CERT_DIR/${name}.cnf"
}

make_cert postgres_server postgres "DNS:citus_coordinator,DNS:citus_worker1,DNS:citus_worker2,DNS:citus_worker3,DNS:citus_worker4,DNS:localhost,IP:127.0.0.1"
make_cert pgbouncer_server pgbouncer "DNS:pgbouncer,DNS:localhost,IP:127.0.0.1"
make_cert pgbouncer_client pgbouncer-client "DNS:pgbouncer-client"
make_cert app_client app-client "DNS:app-client"
make_cert gateway_server localhost "DNS:localhost,IP:127.0.0.1"
make_cert gateway_client gateway-client "DNS:gateway-client"

# Nginx gateway uses a conventional directory; keep copies there.
mkdir -p infra/nginx/certs
cp "$CERT_DIR/ca.crt" infra/nginx/certs/ca.crt
cp "$CERT_DIR/gateway_server.crt" infra/nginx/certs/server.crt
cp "$CERT_DIR/gateway_server.key" infra/nginx/certs/server.key

chmod 0644 "$CERT_DIR"/*.crt infra/nginx/certs/*.crt
chmod 0600 "$CERT_DIR"/*.key infra/nginx/certs/*.key
# The app container runs as a non-root user and bind-mounts this local dev key read-only.
# Production should inject key files with orchestrator-level file ownership/permissions.
chmod 0644 "$CERT_DIR/app_client.key"
cat <<MSG
Generated local TLS/mTLS certificates in ${CERT_DIR} and infra/nginx/certs.
Do not commit generated *.key files. Use real CA/ACME or a platform CA in production.
MSG
