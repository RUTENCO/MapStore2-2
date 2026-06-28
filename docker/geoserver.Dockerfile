FROM kartoza/geoserver:2.21.0

USER root

COPY --chmod=755 docker/geoserver-init.sh /usr/local/bin/geoserver-init.sh

ENTRYPOINT ["/usr/local/bin/geoserver-init.sh"]
