"""init citus schema

Revision ID: 0001_init_schema
Revises:
Create Date: 2026-06-19
"""
from __future__ import annotations

import os

from alembic import op

revision = "0001_init_schema"
down_revision = None
branch_labels = None
depends_on = None


def quote_ident(identifier: str) -> str:
    if not identifier or "\x00" in identifier:
        raise ValueError("Invalid SQL identifier")
    return '"' + identifier.replace('"', '""') + '"'


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citus")
    # Citus DDL in one Alembic transaction can otherwise fail after distributed
    # operations. Keep multi-shard metadata/DDL operations on one connection per node.
    op.execute("SET LOCAL citus.multi_shard_modify_mode TO 'sequential'")

    citus_shard_count = int(os.getenv("CITUS_SHARD_COUNT", "32"))
    op.execute(f"SET citus.shard_count = {citus_shard_count}")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id uuid NOT NULL,
            user_id bigint NOT NULL CHECK (user_id > 0),
            amount numeric(12, 2) NOT NULL CHECK (amount >= 0 AND amount <= 1000000),
            status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'paid', 'cancelled')),
            payload jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(payload) = 'object'),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (user_id, id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS idempotency_keys (
            principal text NOT NULL,
            idempotency_key text NOT NULL,
            request_hash text NOT NULL,
            response jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (principal, idempotency_key),
            CHECK (length(idempotency_key) BETWEEN 16 AND 256)
        )
        """
    )

    op.execute("CREATE INDEX IF NOT EXISTS idx_orders_id ON orders (id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_created_id ON orders (user_id, created_at DESC, id DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_orders_pending_created_id ON orders (created_at DESC, id DESC) WHERE status = 'pending'")
    op.execute("CREATE INDEX IF NOT EXISTS idx_orders_created_at_brin ON orders USING brin (created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_idempotency_created_at ON idempotency_keys (created_at)")


    op.execute(
        """
        DO $$
        BEGIN
            PERFORM 1 FROM pg_dist_partition WHERE logicalrelid = 'orders'::regclass;
            IF NOT FOUND THEN
                PERFORM create_distributed_table('orders', 'user_id');
            END IF;
        END;
        $$
        """
    )
    # Reference table is replicated to every worker; useful for globally checked idempotency.
    op.execute(
        """
        DO $$
        BEGIN
            PERFORM 1 FROM pg_dist_partition WHERE logicalrelid = 'idempotency_keys'::regclass;
            IF NOT FOUND THEN
                PERFORM create_reference_table('idempotency_keys');
            END IF;
        END;
        $$
        """
    )



    app_user = os.getenv("APP_DB_USER", "app_user")
    readonly_user = os.getenv("READONLY_DB_USER", "readonly_user")
    monitoring_user = os.getenv("MONITORING_DB_USER", "monitoring_user")
    backup_user = os.getenv("BACKUP_DB_USER", "backup_user")
    app_role = quote_ident(app_user)
    readonly_role = quote_ident(readonly_user)
    monitoring_role = quote_ident(monitoring_user)
    backup_role = quote_ident(backup_user)
    for role in (app_role, readonly_role):
        op.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON orders TO {app_role}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON idempotency_keys TO {app_role}")
    op.execute(f"GRANT SELECT ON orders TO {readonly_role}")
    op.execute(f"GRANT SELECT ON idempotency_keys TO {readonly_role}")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {monitoring_role}")
    op.execute(f"GRANT SELECT ON orders TO {backup_role}")
    op.execute(f"GRANT SELECT ON idempotency_keys TO {backup_role}")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS idempotency_keys")
    op.execute("DROP TABLE IF EXISTS orders")
