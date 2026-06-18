CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS orders (
    id bigint PRIMARY KEY,
    user_id bigint NOT NULL,
    amount numeric(12, 2) NOT NULL CHECK (amount >= 0),
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'paid', 'cancelled')),
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_orders_user_created
ON orders (user_id, created_at DESC);

-- Partial index: индексируем только маленькое подмножество активных pending-заказов.
CREATE INDEX IF NOT EXISTS idx_orders_pending_created
ON orders (created_at DESC)
WHERE status = 'pending';

-- Для logical decoding лучше иметь publication; pg_logical_slot_get_changes
-- будет читать WAL даже без subscriber.
CREATE PUBLICATION orders_publication FOR TABLE orders;

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_orders_updated_at ON orders;
CREATE TRIGGER trg_orders_updated_at
BEFORE UPDATE ON orders
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
