# Production deployment notes

Docker Compose is provided for local development, demos, and single-node staging. For real production:

1. Run Citus workers on different nodes/availability zones.
2. Use direct coordinator access only for migrations and Citus metadata operations.
3. Use PgBouncer only for application OLTP traffic.
4. Use an external secret manager, not repository files.
5. Enable PITR backup using pgBackRest or Barman.
6. Add alert delivery through Alertmanager/PagerDuty/Opsgenie.
7. Add OpenTelemetry tracing through Tempo/Jaeger.
8. Use NetworkPolicy/firewall rules to block app access to Citus workers.
