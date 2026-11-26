#!/bin/bash
# BookShopWeb entrypoint: deploy the WAR on Tomcat 9, point it at the compose
# database, then run Tomcat in the foreground.
#
# The app reads its connection settings from JVM system properties
# (bookshop.db.*), so every environment-specific value is passed here, from
# compose's environment (which comes from this folder's `.env`), and no
# credential lives in the image. They are added to the CATALINA_OPTS compose
# gives, which already loads the OpenTelemetry agent.
set -euo pipefail

: "${BSW_DB_HOST:?}" "${BSW_DB_NAME:?}" "${BSW_DB_USER:?}" \
  "${BSW_DB_PASSWORD:?}" "${CATALINA_HOME:?}" "${APP_HTTP_PORT:?}" "${CATALINA_OPTS:?}"

# 1. Wait for the database. Its seed is loaded before it reports healthy, but
#    the port is cheap to confirm and makes a startup failure readable.
echo "waiting for db..."
for _ in $(seq 1 120); do
  (echo > "/dev/tcp/${BSW_DB_HOST}/3306") 2>/dev/null && break
  sleep 1
done

# 2. Every link is built from the context path; the WAR's name is that path.
rm -rf "${CATALINA_HOME}/webapps/BookShopWeb" \
  "${CATALINA_HOME}/webapps/BookShopWeb.war"
cp /opt/app/BookShopWeb.war "${CATALINA_HOME}/webapps/BookShopWeb.war"

export CATALINA_OPTS="${CATALINA_OPTS} \
 -Dbookshop.db.host=${BSW_DB_HOST} -Dbookshop.db.port=3306 \
 -Dbookshop.db.name=${BSW_DB_NAME} -Dbookshop.db.user=${BSW_DB_USER} \
 -Dbookshop.db.password=${BSW_DB_PASSWORD} \
 -Dbookshop.image.path=/var/webapp/images"

# The connector listens on the port the stack publishes, so the address the
# browser used also reaches Tomcat from inside: a self-call built from the
# Host header or getServerPort() would otherwise land on a dead port.
SERVER_XML="${CATALINA_HOME}/conf/server.xml"
sed -i -E "s#<Connector port=\"[0-9]+\" protocol=\"HTTP/1.1\"#<Connector port=\"${APP_HTTP_PORT}\" protocol=\"HTTP/1.1\"#" \
  "${SERVER_XML}"
grep -q "<Connector port=\"${APP_HTTP_PORT}\" protocol=\"HTTP/1.1\"" \
  "${SERVER_XML}"

# 3. Foreground, so the container's lifecycle is the app's.
exec "${CATALINA_HOME}/bin/catalina.sh" run
