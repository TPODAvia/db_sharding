#!/usr/bin/env bash
set -euo pipefail

API_KEY="${APP_API_KEY_ADMIN:-${APP_API_KEY:-}}"
API_HEADER=()
if [[ -n "$API_KEY" ]]; then
  API_HEADER=(-H "x-api-key: ${API_KEY}")
fi

BASE_WRITE="${BASE_WRITE:-http://localhost:8001/api/v1}"
BASE_READ="${BASE_READ:-http://localhost:8002/api/v1}"

IDEMPOTENCY_KEY="demo-$(date +%s)-$RANDOM-$RANDOM"

echo "Create order. Citus routes by distribution column user_id."
ORDER_JSON=$(curl -s -X POST "${BASE_WRITE}/orders" \
  -H 'Content-Type: application/json' \
  -H "Idempotency-Key: ${IDEMPOTENCY_KEY}" \
  "${API_HEADER[@]}" \
  -d '{"user_id": 42, "amount": 123.45, "status": "pending", "payload": {"demo": true}}')
echo "$ORDER_JSON" | python3 -m json.tool
ORDER_ID=$(ORDER_JSON="$ORDER_JSON" python3 - <<'PY'
import json
import os
print(json.loads(os.environ["ORDER_JSON"])["id"])
PY
)

echo
echo "Read user orders through reader service"
curl -s "${API_HEADER[@]}" "${BASE_READ}/users/42/orders" | python3 -m json.tool

echo
echo "Read one order using user_id + UUIDv7 id, the scalable Citus path"
curl -s "${API_HEADER[@]}" "${BASE_READ}/users/42/orders/${ORDER_ID}" | python3 -m json.tool

echo
echo "Admin-only fan-out pending orders"
curl -s "${API_HEADER[@]}" "${BASE_READ}/admin/orders/pending" | python3 -m json.tool
