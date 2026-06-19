from __future__ import annotations

import time

import jwt


def test_jwt_contains_tenant_claim() -> None:
    secret = "test-secret-with-at-least-32-bytes-long"
    payload = {
        "sub": "user-42",
        "tenant_id": 42,
        "roles": ["orders:read"],
        "iat": int(time.time()),
        "exp": int(time.time()) + 60,
        "iss": "orders-demo",
        "aud": "orders-api",
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    decoded = jwt.decode(token, secret, algorithms=["HS256"], issuer="orders-demo", audience="orders-api")
    assert decoded["tenant_id"] == 42
    assert "orders:read" in decoded["roles"]
