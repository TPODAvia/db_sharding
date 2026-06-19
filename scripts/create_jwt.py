#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import jwt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.common.env import get_env_or_file  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an HS256 JWT for local/admin usage.")
    parser.add_argument("--sub", default="admin")
    parser.add_argument("--roles", default="admin,orders:read,orders:write")
    parser.add_argument("--tenant-id", type=int, default=None, help="Tenant/user id claim for tenant-scoped access")
    parser.add_argument("--ttl-seconds", type=int, default=3600)
    parser.add_argument("--issuer", default=os.getenv("JWT_ISSUER", "orders-demo"))
    parser.add_argument("--audience", default=os.getenv("JWT_AUDIENCE", "orders-api"))
    args = parser.parse_args()

    secret = get_env_or_file("JWT_SECRET")
    if not secret:
        raise SystemExit("JWT_SECRET or JWT_SECRET_FILE is required")
    now = int(time.time())
    payload = {
        "sub": args.sub,
        "roles": [r.strip() for r in args.roles.split(",") if r.strip()],
        "iat": now,
        "exp": now + args.ttl_seconds,
        "iss": args.issuer,
        "aud": args.audience,
    }
    if args.tenant_id is not None:
        payload["tenant_id"] = args.tenant_id
    print(jwt.encode(payload, secret, algorithm="HS256", headers={"typ": "JWT"}))


if __name__ == "__main__":
    main()
