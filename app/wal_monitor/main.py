from __future__ import annotations

import logging
import os
import time

import psycopg

from app.common.env import get_env_or_file

USER = os.environ["PGUSER"]
PASSWORD = get_env_or_file("PGPASSWORD") or ""
DATABASE = os.getenv("PGDATABASE", "gr5")
HOST = os.getenv("POSTGRES_HOST", "citus_coordinator")
POLL_SECONDS = float(os.getenv("WAL_POLL_SECONDS", "3"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)


def connect() -> psycopg.Connection:
    return psycopg.connect(
        host=HOST,
        port=5432,
        dbname=DATABASE,
        user=USER,
        password=PASSWORD,
        autocommit=True,
        connect_timeout=10,
    )


def read_cluster_status(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT pg_current_wal_lsn()")
        current_lsn = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM citus_get_active_worker_nodes()")
        active_workers = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM pg_dist_shard")
        distributed_shards = cur.fetchone()[0]
        logger.info(
            "coordinator_wal_lsn=%s active_workers=%s distributed_shards=%s",
            current_lsn,
            active_workers,
            distributed_shards,
        )


def main() -> None:
    conn = connect()
    while True:
        try:
            read_cluster_status(conn)
        except Exception:  # noqa: BLE001
            logger.exception("Citus status read failed; reconnecting")
            conn.close()
            conn = connect()
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
