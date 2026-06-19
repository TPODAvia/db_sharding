FROM alpine:3.20
RUN apk add --no-cache pgbouncer gettext su-exec && \
    addgroup -S pgbouncer && \
    adduser -S -G pgbouncer pgbouncer && \
    mkdir -p /etc/pgbouncer /var/run/pgbouncer /var/lib/pgbouncer/tls /usr/local/share/pgbouncer && \
    chown -R pgbouncer:pgbouncer /etc/pgbouncer /var/run/pgbouncer /var/lib/pgbouncer /usr/local/share/pgbouncer
COPY pgbouncer.ini.template /usr/local/share/pgbouncer/pgbouncer.ini.template
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
EXPOSE 6432
ENTRYPOINT ["/entrypoint.sh"]
