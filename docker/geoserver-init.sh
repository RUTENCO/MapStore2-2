#!/bin/bash

(
  GLOBAL_XML=/opt/geoserver/data_dir/global.xml

  while [ ! -f "$GLOBAL_XML" ]; do
    sleep 2
  done

  sed -i \
  's#<useHeadersProxyURL>false</useHeadersProxyURL>#<useHeadersProxyURL>true</useHeadersProxyURL>#g' \
  "$GLOBAL_XML"

  if ! grep -q "<proxyBaseUrl>" "$GLOBAL_XML"; then
    sed -i \
    "s#<globalServices>true</globalServices>#<globalServices>true</globalServices><proxyBaseUrl>https://${PUBLIC_HOST}/geoserver</proxyBaseUrl>#g" \
    "$GLOBAL_XML"
  fi

  echo "[GeoServer Init] Proxy configuration applied"

) &

exec /scripts/entrypoint.sh
