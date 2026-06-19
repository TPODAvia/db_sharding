# Backup/restore runbook

## Logical Citus backup

```bash
./scripts/backup_all_shards.sh
latest=$(ls -dt shared/backups/* | head -1)
./scripts/verify_backup.sh "$latest"
./scripts/backup_restore_drill.sh "$latest"
```

`backup_all_shards.sh` creates:

- `coordinator.dump` in custom `pg_dump` format;
- `manifest.json` with backup metadata;
- `cluster_state.txt` with Citus state;
- `SHA256SUMS` for integrity verification.

## Restore to production database

Stop writes first, test restore in a drill, then run:

```bash
RESTORE_CONFIRM=I_UNDERSTAND_THIS_REPLACES_DATA ./scripts/restore_citus_backup.sh shared/backups/<backup_id>
```

## Physical backup / PITR

For large production datasets use pgBackRest stanzas for coordinator and every worker:

```bash
./scripts/backup_full.sh
./scripts/verify_backup.sh
./scripts/restore_pitr.sh '2026-06-19 10:00:00+00'
```

Coordinator and all workers must be restored to the same target time. Keep application traffic stopped until Citus metadata and smoke checks pass.

Production policy:

- define RPO/RTO;
- schedule full/differential/incremental backups;
- archive WAL to object storage;
- alert on failed backups and stale backups;
- run restore drills regularly.
