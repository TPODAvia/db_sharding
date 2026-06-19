Put TLS files here for the optional `gateway` profile:

- `server.crt`
- `server.key`
- `ca.crt` for mTLS client certificate verification

For local testing only, create self-signed certificates. For production, use a
real CA/ACME flow or terminate TLS at a managed load balancer/API gateway.
