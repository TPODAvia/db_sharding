from __future__ import annotations


def shard_number_for_user(user_id: int, shard_count: int) -> int:
    """Returns human shard number: 1..N."""
    if shard_count <= 0:
        raise ValueError("shard_count must be positive")
    return (user_id % shard_count) + 1


def shard_database_name(shard_number: int) -> str:
    return f"shard{shard_number}"