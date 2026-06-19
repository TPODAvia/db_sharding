ARG CITUS_IMAGE=citusdata/citus:14-pg16
FROM ${CITUS_IMAGE}
USER root
COPY infra/citus/tls-entrypoint.sh /usr/local/bin/tls-entrypoint.sh
RUN chmod +x /usr/local/bin/tls-entrypoint.sh
ENTRYPOINT ["/usr/local/bin/tls-entrypoint.sh"]
CMD ["postgres"]
