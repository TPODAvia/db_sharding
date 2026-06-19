# Integration tests

Run locally after Docker is available:

```bash
./scripts/init_citus_cluster.sh 2
pytest
cat tests/integration/test_citus_cluster.sql | docker compose -f docker-compose.yml -f docker-compose.workers.yml exec -T citus_coordinator psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1
```
