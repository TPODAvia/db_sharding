from __future__ import annotations

import os
import time

import psycopg

USER = os.getenv("PGUSER", "gr5")
PASSWORD = os.getenv("PGPASSWORD", "admin")
DATABASE = os.getenv("PGDATABASE", "gr5")
POLL_SECONDS = float(os.getenv("WAL_POLL_SECONDS", "3"))
SHARDS = [
    (1, os.getenv("SHARD1_HOST", "postgres_shard1")),
    (2, os.getenv("SHARD2_HOST", "postgres_shard2")),
]


def connect(host: str) -> psycopg.Connection:
    return psycopg.connect(
        host=host,
        port=5432,
        dbname=DATABASE,
        user=USER,
        password=PASSWORD,
        autocommit=True,
    )


def ensure_slot(conn: psycopg.Connection, slot_name: str) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_replication_slots WHERE slot_name = %s", (slot_name,))
        if cur.fetchone() is None:
            cur.execute("SELECT pg_create_logical_replication_slot(%s, 'test_decoding')", (slot_name,))


def read_changes(conn: psycopg.Connection, slot_name: str, shard_number: int) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT pg_current_wal_lsn()")
        current_lsn = cur.fetchone()[0]
        cur.execute("SELECT lsn, xid, data FROM pg_logical_slot_get_changes(%s, NULL, 20)", (slot_name,))
        rows = cur.fetchall()
        if not rows:
            print(f"shard={shard_number} current_wal_lsn={current_lsn} no new decoded WAL changes", flush=True)
            return
        for lsn, xid, data in rows:
            print(f"shard={shard_number} lsn={lsn} xid={xid} data={data}", flush=True)


def main() -> None:
    connections: list[tuple[int, psycopg.Connection, str]] = []
    for shard_number, host in SHARDS:
        conn = connect(host)
        slot_name = f"orders_slot_s{shard_number}"
        ensure_slot(conn, slot_name)
        connections.append((shard_number, conn, slot_name))
        print(f"logical decoding slot ready: shard={shard_number} slot={slot_name}", flush=True)

    while True:
        for shard_number, conn, slot_name in connections:
            read_changes(conn, slot_name, shard_number)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
