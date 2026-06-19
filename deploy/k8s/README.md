# Kubernetes deployment skeleton

This project is Docker Compose runnable, but real production should run on an orchestrator.
Use this directory as a placeholder for Helm/Kustomize manifests. Recommended split:

- managed PostgreSQL/Citus where possible;
- app deployments for writer/reader with HPA;
- PgBouncer deployment with PodDisruptionBudget;
- Nginx/Ingress with TLS/mTLS termination;
- ExternalSecret/SealedSecret for secrets;
- PrometheusRule and ServiceMonitor objects;
- NetworkPolicy to block direct worker access.
