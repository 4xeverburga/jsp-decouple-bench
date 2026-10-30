#!/bin/bash
# OpenClinica app entrypoint: explode the WAR, point it at the compose
# database and at the URL the host actually reaches, then run Tomcat 9.
#
# The WAR is built in the image with placeholder db settings; every
# environment-specific value is written here, from compose's environment
# (which comes from this folder's `.env`), so no credential lives in the image.
set -euo pipefail

: "${OPENCLINICA_PUBLIC_URL:?}" "${OPENCLINICA_DB_HOST:?}" \
  "${OPENCLINICA_DB_NAME:?}" "${OPENCLINICA_DB_USER:?}" \
  "${OPENCLINICA_DB_PASSWORD:?}" "${CATALINA_HOME:?}"

APP="${CATALINA_HOME}/webapps/OpenClinica"

# 1. Wait for the database. Liquibase creates the whole schema while the app
#    boots, so it must be reachable before Tomcat starts the context.
echo "waiting for db..."
for _ in $(seq 1 120); do
  (echo > "/dev/tcp/${OPENCLINICA_DB_HOST}/5432") 2>/dev/null && break
  sleep 1
done

# 2. Explode the WAR ourselves. The properties below have to be rewritten
#    before Spring reads them, and Tomcat would only explode it on start.
rm -rf "${APP}"
mkdir -p "${APP}"
(cd "${APP}" && jar xf /opt/openclinica/OpenClinica.war)

PROPS="${APP}/WEB-INF/classes/datainfo.properties"
# NOTE: a `#` in a value would break sed here — keep the sample credentials
# alphanumeric (they are synthetic, so this costs nothing).
sed -i \
  -e "s#^dbType=.*#dbType=postgres#" \
  -e "s#^dbHost=.*#dbHost=${OPENCLINICA_DB_HOST}#" \
  -e "s#^dbPort=.*#dbPort=5432#" \
  -e "s#^db=.*#db=${OPENCLINICA_DB_NAME}#" \
  -e "s#^dbUser=.*#dbUser=${OPENCLINICA_DB_USER}#" \
  -e "s#^dbPass=.*#dbPass=${OPENCLINICA_DB_PASSWORD}#" \
  -e "s#^sysURL=.*#sysURL=${OPENCLINICA_PUBLIC_URL}/OpenClinica/MainMenu#" \
  "${PROPS}"

# 3. Foreground, so the container's lifecycle is the app's.
exec "${CATALINA_HOME}/bin/catalina.sh" run
