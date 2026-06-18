# PostgreSQL + PgBouncer + Snowflake ID + Sharding + WAL demo

Это учебный, но рабочий проект.

Внутри:

- `postgres_shard1` — PostgreSQL shard 1, `pgvector/pgvector:pg16`
- `postgres_shard2` — PostgreSQL shard 2, `pgvector/pgvector:pg16`
- `pgbouncer` — connection pooler перед шардами
- `writer_service` — Python FastAPI сервис, создаёт заказы
- `reader_service` — Python FastAPI сервис, читает заказы
- `producer_service` — отдельная Python-система, постоянно создаёт тестовые заказы
- `wal_monitor` — читает WAL через logical decoding `test_decoding`

## Архитектура

```text
                ┌─────────────────────┐
                │   writer_service     │
                │   Snowflake ID       │
                └──────────┬──────────┘
                           │
                ┌──────────▼──────────┐
                │      PgBouncer       │
                │ db=shard1 / shard2   │
                └──────┬────────┬─────┘
                       │        │
          ┌────────────▼─┐    ┌─▼────────────┐
          │ postgres_s1  │    │ postgres_s2  │
          │ WAL logical  │    │ WAL logical  │
          └──────────────┘    └──────────────┘
```

Шард выбирается в приложении:

```python
shard_number = (user_id % SHARD_COUNT) + 1
```

То есть при `SHARD_COUNT=2`:

```text
user_id=1 -> shard2
user_id=2 -> shard1
user_id=3 -> shard2
user_id=4 -> shard1
```

## Запуск

```bash
cp .env.example .env
mkdir -p shared/data/postgres_shard1 shared/data/postgres_shard2
docker compose up --build
```

Порты:

```text
5433 -> postgres_shard1 напрямую
5434 -> postgres_shard2 напрямую
6432 -> PgBouncer
8001 -> writer_service
8002 -> reader_service
```

## Проверка

Создать заказ:

```bash
curl -X POST http://localhost:8001/orders \
  -H 'Content-Type: application/json' \
  -d '{"user_id": 1, "amount": 123.45, "status": "pending", "payload": {"source": "manual"}}'
```

Прочитать заказы пользователя:

```bash
curl http://localhost:8002/users/1/orders
```

Получить pending-заказы:

```bash
curl http://localhost:8002/orders/pending
```

Запустить готовый demo script:

```bash
./scripts/demo.sh
```

## Где здесь Snowflake ID

Файл:

```text
app/common/snowflake.py
```

Схема ID:

```text
41 bits timestamp millis since 2024-01-01
10 bits worker_id
12 bits sequence
```

`writer_service` использует:

```text
SNOWFLAKE_WORKER_ID=1
```

`producer_service` использует:

```text
SNOWFLAKE_WORKER_ID=3
```

Важно: в реальных системах нельзя давать двум работающим инстансам одинаковый `worker_id`.

## Где здесь sharding

Файл:

```text
app/common/sharding.py
```

Логика:

```python
shard_number = (user_id % shard_count) + 1
```

База в PgBouncer выбирается так:

```text
shard1 -> postgres_shard1:5432/gr5
shard2 -> postgres_shard2:5432/gr5
```

Конфиг:

```text
infra/pgbouncer/pgbouncer.ini
```

## Где здесь PgBouncer

PgBouncer принимает подключения на `localhost:6432`.

Пулы:

```ini
[databases]
shard1 = host=postgres_shard1 port=5432 dbname=gr5
shard2 = host=postgres_shard2 port=5432 dbname=gr5
```

Python подключается не к PostgreSQL напрямую, а к PgBouncer:

```text
host=pgbouncer
port=6432
database=shard1 или shard2
```

В `asyncpg` отключён statement cache:

```python
statement_cache_size=0
```

Это важно для PgBouncer в `transaction` pooling mode.

## Где здесь WAL

Оба PostgreSQL запускаются с настройками:

```text
wal_level=logical
max_wal_senders=10
max_replication_slots=10
```

`wal_monitor` подключается напрямую к каждому PostgreSQL и создаёт logical replication slot:

```sql
SELECT pg_create_logical_replication_slot('orders_slot_s1', 'test_decoding');
```

Потом читает изменения:

```sql
SELECT lsn, xid, data
FROM pg_logical_slot_get_changes('orders_slot_s1', NULL, 20);
```

В логах будет видно примерно такое:

```text
shard=1 lsn=0/199A8D8 xid=742 data=table public.orders: INSERT: id[bigint]:...
```

Смотреть логи:

```bash
docker compose logs -f wal_monitor
```

## Где partial index

Файл:

```text
infra/postgres/init/001_schema.sql
```

Индекс:

```sql
CREATE INDEX IF NOT EXISTS idx_orders_pending_created
ON orders (created_at DESC)
WHERE status = 'pending';
```

Он используется для запроса:

```sql
SELECT *
FROM orders
WHERE status = 'pending'
ORDER BY created_at DESC;
```

Проверить напрямую:

```bash
docker exec -it postgres_shard1 psql -U gr5 -d gr5
```

```sql
EXPLAIN ANALYZE
SELECT id, user_id, amount, status, created_at
FROM orders
WHERE status = 'pending'
ORDER BY created_at DESC
LIMIT 20;
```

## Важное ограничение проекта

Это учебная app-level sharding схема.

PgBouncer не умеет сам понимать, в какой shard отправить конкретный `user_id`. Роутинг делает приложение:

```text
Python выбирает shard -> подключается к database=shard1 или database=shard2 в PgBouncer
```

В production дополнительно нужны:

- миграции через Alembic на каждый shard;
- нормальный service discovery для `worker_id`;
- мониторинг replication slots, потому что забытый slot может удерживать WAL;
- backups на каждый shard;
- rebalancing strategy при добавлении новых шардов;
- отдельные read replicas, если нужен read scaling.

## Полезные команды

Остановить:

```bash
docker compose down
```

Остановить и удалить данные:

```bash
docker compose down -v
rm -rf shared/data/postgres_shard1 shared/data/postgres_shard2
```

Проверить PgBouncer:

```bash
psql 'postgresql://gr5:admin@localhost:6432/pgbouncer' -c 'SHOW POOLS;'
```

Подключиться к shard1 через PgBouncer:

```bash
psql 'postgresql://gr5:admin@localhost:6432/shard1'
```

Подключиться к shard2 через PgBouncer:

```bash
psql 'postgresql://gr5:admin@localhost:6432/shard2'
```
