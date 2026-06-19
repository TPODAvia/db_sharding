# Old manual shard migration removed

В этой версии проекта больше нет ручных `postgres_shard1/postgres_shard2/postgres_shard3`, `user_shard_map` и кастомного router.

Вместо этого используется Citus:

```text
FastAPI -> PgBouncer -> Citus coordinator -> Citus workers
```

## Добавить новую worker-ноду

```bash
./scripts/add_citus_worker.sh 3
```

Это заменяет старый сценарий `add_shard.sh`.

## Перенос данных

Раньше нужно было вручную переносить пользователя между шардами. Теперь Citus сам хранит metadata placements, а перераспределение выполняется так:

```sql
SELECT rebalance_table_shards('orders');
```

Скрипт `add_citus_worker.sh` делает это автоматически, если не передать:

```bash
REBALANCE_AFTER_ADD=false ./scripts/add_citus_worker.sh 3
```
