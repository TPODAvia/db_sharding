from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from app.common.repository import idempotency_request_hash, to_jsonb


def test_to_jsonb_serializes_production_types() -> None:
    raw = {
        "id": UUID("018f0000-0000-7000-8000-000000000001"),
        "amount": Decimal("10.50"),
        "created_at": datetime(2026, 6, 19, 8, 0, tzinfo=UTC),
    }
    encoded = to_jsonb(raw)
    decoded = json.loads(encoded)
    assert decoded["id"] == "018f0000-0000-7000-8000-000000000001"
    assert decoded["amount"] == "10.50"
    assert decoded["created_at"].startswith("2026-06-19T08:00:00")


def test_idempotency_hash_is_stable_for_equal_payloads() -> None:
    left = idempotency_request_hash(user_id=42, amount=Decimal("1.00"), status="pending", payload={"b": 2, "a": 1})
    right = idempotency_request_hash(user_id=42, amount=Decimal("1.00"), status="pending", payload={"a": 1, "b": 2})
    assert left == right


def test_idempotency_hash_changes_for_different_payload() -> None:
    left = idempotency_request_hash(user_id=42, amount=Decimal("1.00"), status="pending", payload={"a": 1})
    right = idempotency_request_hash(user_id=42, amount=Decimal("2.00"), status="pending", payload={"a": 1})
    assert left != right
