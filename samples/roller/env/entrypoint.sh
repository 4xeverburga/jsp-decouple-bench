#!/bin/bash
# Roller entrypoint: load the schema on a fresh database, write Roller's
# config, deploy the app on Tomcat 9, then run Tomcat in the foreground.
#
# Every environment-specific value is written here, from compose's
# environment (which comes from this folder's `.env`), so no credential lives
# in the image.
set -euo pipefail

: "${ROLLER_DB_HOST:?}" "${ROLLER_DB_NAME:?}" "${ROLLER_DB_USER:?}" \
  "${ROLLER_DB_PASSWORD:?}" "${CATALINA_HOME:?}" "${APP_HTTP_PORT:?}"

MYSQL=(mysql -h "${ROLLER_DB_HOST}" -u"${ROLLER_DB_USER}" \
  -p"${ROLLER_DB_PASSWORD}" --default-character-set=utf8)

# 1. Wait for the database.
echo "waiting for db..."
for _ in $(seq 1 120); do
  "${MYSQL[@]}" -e 'SELECT 1' >/dev/null 2>&1 && break
  sleep 1
done

# 2. A fresh volume has no tables. The schema is the build's own
#    (createdb.vm rendered for MySQL), so it comes from the image, not the
#    db service. `installation.type=manual` below expects it in place.
TABLES=$("${MYSQL[@]}" -N -e "SELECT COUNT(*) FROM information_schema.tables
  WHERE table_schema = '${ROLLER_DB_NAME}'")
if [ "${TABLES}" = "0" ]; then
  echo "loading schema..."
  "${MYSQL[@]}" "${ROLLER_DB_NAME}" < /opt/app/createdb.sql
fi

# 3. Roller reads roller-custom.properties from Tomcat's classpath.
cat > "${CATALINA_HOME}/lib/roller-custom.properties" <<PROPS
installation.type=manual
database.configurationType=jdbc
database.jdbc.driverClass=com.mysql.jdbc.Driver
database.jdbc.connectionURL=jdbc:mysql://${ROLLER_DB_HOST}:3306/${ROLLER_DB_NAME}?autoReconnect=true&useUnicode=true&characterEncoding=utf-8&mysqlEncoding=utf8&useSSL=false
database.jdbc.username=${ROLLER_DB_USER}
database.jdbc.password=${ROLLER_DB_PASSWORD}
mail.configurationType=properties
mail.hostname=localhost
mediafiles.storage.dir=/var/lib/roller/mediafiles
search.index.dir=/var/lib/roller/search-index
cache.dir=/var/lib/roller/planet-cache
log4j.appender.roller.File=${CATALINA_HOME}/logs/roller.log
PROPS

# 4. The exploded app (see Containerfile), deployed under its own name: the
#    context path is /roller.
rm -rf "${CATALINA_HOME}/webapps/roller"
cp -r /opt/app/roller "${CATALINA_HOME}/webapps/roller"

# The connector listens on the port the stack publishes, so the address the
# browser used also reaches Tomcat from inside: a self-call built from the
# Host header or getServerPort() would otherwise land on a dead port.
SERVER_XML="${CATALINA_HOME}/conf/server.xml"
sed -i -E "s#<Connector port=\"[0-9]+\" protocol=\"HTTP/1.1\"#<Connector port=\"${APP_HTTP_PORT}\" protocol=\"HTTP/1.1\"#" \
  "${SERVER_XML}"
grep -q "<Connector port=\"${APP_HTTP_PORT}\" protocol=\"HTTP/1.1\"" \
  "${SERVER_XML}"

# 5. Foreground, so the container's lifecycle is the app's.
exec "${CATALINA_HOME}/bin/catalina.sh" run
