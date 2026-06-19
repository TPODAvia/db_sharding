# Runtime hardening runbook

The compose stack uses:

- non-root application and PgBouncer images;
- `read_only: true` where supported;
- `tmpfs` for writable runtime paths;
- `no-new-privileges:true`;
- `cap_drop: [ALL]`;
- process, CPU, and memory limits;
- local-only port bindings for internal services.

Production additions usually handled by the platform:

- seccomp/AppArmor/SELinux profiles;
- Kubernetes Pod Security Admission restricted profile;
- network policies;
- image admission control;
- external secret injection;
- read-only root filesystem enforcement;
- central log collection.
