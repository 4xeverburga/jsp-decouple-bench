#!/bin/bash
# Online Study System entrypoint: deploy the WAR on Tomcat 9, point it at the
# compose database, then run Tomcat in the foreground.
#
# The WAR is built in the image with whatever datasource the tree carries;
# every environment-specific value is written here, from compose's environment
# (which comes from this folder's `.env`), so no credential lives in the image.
#
# Only the four connection keys are replaced, and they are matched with
# optional spaces around `=` because the tree's own file spells them
# `jdbc.url = ...`. Anything else the tree put in this file is left alone.
set -euo pipefail

: "${OSS_DB_HOST:?}" "${OSS_DB_NAME:?}" "${OSS_DB_USER:?}" \
  "${OSS_DB_PASSWORD:?}" "${CATALINA_HOME:?}"

APP="${CATALINA_HOME}/webapps/Examination_System"

# 1. Wait for the database. Its seed is loaded before it reports healthy, but
#    the port is cheap to confirm and makes a startup failure readable.
echo "waiting for db..."
for _ in $(seq 1 120); do
  (echo > "/dev/tcp/${OSS_DB_HOST}/3306") 2>/dev/null && break
  sleep 1
done

# 2. Explode the WAR ourselves: Spring reads the datasource from the classpath
#    properties, which Tomcat would only explode on start.
rm -rf "${APP}" "${APP}.war"
mkdir -p "${APP}"
(cd "${APP}" && jar xf /opt/app/Examination_System.war)

PROPS="${APP}/WEB-INF/classes/mysql.properties"
# NOTE: `&` in the URL is escaped — sed reads it as "the whole match".
sed -i -E \
  -e "s#^[[:space:]]*jdbc\.driver[[:space:]]*=.*#jdbc.driver = com.mysql.jdbc.Driver#" \
  -e "s#^[[:space:]]*jdbc\.url[[:space:]]*=.*#jdbc.url = jdbc:mysql://${OSS_DB_HOST}:3306/${OSS_DB_NAME}?useUnicode=true\&characterEncoding=utf8\&useSSL=false#" \
  -e "s#^[[:space:]]*jdbc\.username[[:space:]]*=.*#jdbc.username = ${OSS_DB_USER}#" \
  -e "s#^[[:space:]]*jdbc\.password[[:space:]]*=.*#jdbc.password = ${OSS_DB_PASSWORD}#" \
  "${PROPS}"

# 3. Foreground, so the container's lifecycle is the app's.
exec "${CATALINA_HOME}/bin/catalina.sh" run
