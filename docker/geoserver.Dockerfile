FROM kartoza/geoserver:2.21.0

COPY docker/geoserver-init.sh /usr/local/bin/geoserver-init.sh

RUN chmod +x /usr/local/bin/geoserver-init.sh
