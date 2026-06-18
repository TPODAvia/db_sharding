#!/usr/bin/env bash
set -euo pipefail

echo "Create order for user_id=1. user_id % 2 => shard2"
curl -s -X POST http://localhost:8001/orders \
    -H 'Content-Type: application/json' \
    -d '{"user_id": 1, "amount": 123.45, "status": "pending", "payload": {"demo": true}}' | python3 -m json.tool

echo

echo "Create order for user_id=2. user_id % 2 => shard1"
curl -s -X POST http://localhost:8001/orders \
  -H 'Content-Type: application/json' \
  -d '{"user_id": 2, "amount": 50.00, "status": "paid", "payload": {"demo": true}}' | python3 -m json.tool

echo

echo "Read user orders through reader service"
curl -s http://localhost:8002/users/1/orders | python3 -m json.tool

echo

echo "Read pending orders. This uses partial index on every shard."
curl -s http://localhost:8002/orders/pending | python3 -m json.tool
