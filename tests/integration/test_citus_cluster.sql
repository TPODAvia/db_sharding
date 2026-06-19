-- Run after ./scripts/init_citus_cluster.sh
SELECT count(*) >= 1 AS has_workers FROM citus_get_active_worker_nodes();
SELECT logicalrelid::regclass FROM pg_dist_partition WHERE logicalrelid = 'orders'::regclass;
SELECT count(*) > 0 AS has_shards FROM pg_dist_shard;
