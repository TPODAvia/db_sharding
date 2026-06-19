FROM alpine:3.20
RUN apk add --no-cache pgbouncer gettext su-exec && \
    addgroup -S pgbouncer && \
    adduser -S -G pgbouncer pgbouncer && \
    mkdir -p /etc/pgbouncer /var/run/pgbouncer /var/lib/pgbouncer/tls && \
    chown -R pgbouncer:pgbouncer /etc/pgbouncer /var/run/pgbouncer /var/lib/pgbouncer
COPY pgbouncer.ini.template /etc/pgbouncer/pgbouncer.ini.template
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
EXPOSE 6432
ENTRYPOINT ["/entrypoint.sh"]
