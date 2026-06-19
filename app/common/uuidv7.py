from __future__ import annotations

import secrets
import time
from uuid import UUID


def new_uuidv7() -> UUID:
    """Generate a time-ordered UUIDv7.

    The project targets Citus on PostgreSQL 16, so UUIDv7 is generated in the
    application. PostgreSQL 18+ can replace this wrapper with native uuidv7().
    Layout follows RFC 9562 UUIDv7: 48-bit Unix epoch milliseconds + version +
    random bits. The random component is generated with the OS CSPRNG.
    """

    timestamp_ms = int(time.time() * 1000) & ((1 << 48) - 1)
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)
    value = (timestamp_ms << 80) | (0x7 << 76) | (rand_a << 64) | (0b10 << 62) | rand_b
    return UUID(int=value)
