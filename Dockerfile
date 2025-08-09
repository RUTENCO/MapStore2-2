FROM tomcat:9-jdk11 AS mother
LABEL maintainer="Alessandro Parma<alessandro.parma@geosolutionsgroup.com>"
ARG MAPSTORE_WEBAPP_SRC="./product/target/mapstore.war"
ADD "${MAPSTORE_WEBAPP_SRC}" "/mapstore/"
COPY ./docker/* /mapstore/docker/
WORKDIR /mapstore

FROM tomcat:9-jdk11
ARG UID=1001
ARG GID=1001
ARG UNAME=tomcat

# aseguramos la ruta real
ENV CATALINA_BASE=/usr/local/tomcat
ENV MAPSTORE_WEBAPP_DST="${CATALINA_BASE}/webapps"
ARG INITIAL_MEMORY="512m"
ARG MAXIMUM_MEMORY="512m"
ENV JAVA_OPTS="${JAVA_OPTS} -Xms${INITIAL_MEMORY} -Xmx${MAXIMUM_MEMORY}"
ARG OVR="geostore-datasource-ovr-postgres.properties"
ENV GEOSTORE_OVR_OPT="-Dgeostore-ovr=file://${CATALINA_BASE}/conf/${OVR}"
ARG DATA_DIR="${CATALINA_BASE}/datadir"
ENV JAVA_OPTS="${JAVA_OPTS} ${GEOSTORE_OVR_OPT} -Ddatadir.location=${DATA_DIR}"
ENV TERM=xterm

# --- limpiar cualquier exploded app o caches previos antes de copiar el WAR ---
USER root
RUN rm -rf ${CATALINA_BASE}/webapps/mapstore ${CATALINA_BASE}/work/Catalina || true

# copiar el nuevo WAR (ya garantizamos que no haya exploded antiguo)
COPY --from=mother "/mapstore/mapstore.war" "${MAPSTORE_WEBAPP_DST}/mapstore.war"
COPY --from=mother "/mapstore/docker" "${CATALINA_BASE}/docker/"

COPY binary/tomcat/conf/server.xml "${CATALINA_BASE}/conf/"
RUN sed -i -e 's/8082/8080/g' ${CATALINA_BASE}/conf/server.xml

RUN mkdir -p ${DATA_DIR}
RUN cp ${CATALINA_BASE}/docker/wait-for-postgres.sh /usr/bin/wait-for-postgres
RUN chmod +x /usr/bin/wait-for-postgres

# ... resto de apt-get, creación de usuario, chown, etc (igual que antes) ...
RUN apt-get update \
    && apt-get install --yes postgresql-client \
    && apt-get clean \
    && rm -rf /var/cache/apt/* /var/lib/apt/lists/* /usr/share/man/* /usr/share/doc/*
RUN groupadd -g $GID $UNAME
RUN useradd -m -u $UID -g $GID --system $UNAME
RUN chown -R $UID:$GID ${CATALINA_BASE} ${MAPSTORE_WEBAPP_DST} ${DATA_DIR}
USER $UNAME
WORKDIR ${CATALINA_BASE}

VOLUME [ "${DATA_DIR}" ]
EXPOSE 8080
