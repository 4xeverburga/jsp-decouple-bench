#!/usr/bin/env bash
# Reset the openclinica stack to pristine seed state (for golden-delta capture
# and coverage runs — NOT part of the e2e test contract, which forbids DB
# drops inside tests). Mirrors test-admin-from-scratch.sh steps 1-2 + bootstrap:
# stop Tomcat -> drop/recreate DB -> start Tomcat (Liquibase re-seeds) ->
# rotate the admin credential.
set -euo pipefail

ENV_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BENCH="$(cd "$ENV_DIR/../.." && pwd)"
# shellcheck disable=SC1090
source "$ENV_DIR/.env"
TC="${OPENCLINICA_TOMCAT_HOME:-/home/ever/tools/apache-tomcat-oc}"
APP_URL="http://localhost:${OPENCLINICA_HTTP_PORT:-8089}/OpenClinica"

echo "== 1. stop Tomcat, drop + recreate the database"
"$TC/bin/catalina.sh" stop -force >/dev/null 2>&1 || true
# wait until the HTTP port is actually released (shutdown can outlive the
# stop command; starting too early fails with Address already in use)
PORT="${OPENCLINICA_HTTP_PORT:-8089}"
for _ in $(seq 1 60); do
  curl -s -o /dev/null --max-time 2 "localhost:$PORT" || break
  sleep 1
done
sleep 3
podman exec openclinica-pg psql -U clinica -d postgres -v ON_ERROR_STOP=1 -q \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='openclinica' AND pid <> pg_backend_pid();" \
  -c "DROP DATABASE IF EXISTS openclinica;" \
  -c "CREATE DATABASE openclinica OWNER clinica;"

echo "== 2. start Tomcat -> Liquibase re-seeds schema"
JAVA_HOME="${JDK8:-/usr/lib/jvm/jdk-8.0.202-oracle-x64}" \
  CATALINA_HOME="$TC" CATALINA_BASE="$TC" "$TC/bin/catalina.sh" start >/dev/null
for _ in $(seq 1 60); do
  CODE=$(curl -s -o /dev/null -w '%{http_code}' "$APP_URL/pages/login/login" --max-time 5 || true)
  TABLES=$(podman exec openclinica-pg psql -U clinica -d openclinica -t -A -c \
    "select count(*) from information_schema.tables where table_schema='public';" 2>/dev/null || echo 0)
  if [[ "$CODE" == "200" && "$TABLES" -ge 100 ]]; then break; fi
  sleep 3
done
[[ "$CODE" == "200" && "$TABLES" -ge 100 ]] || { echo "FAIL: app/schema not ready"; exit 1; }
echo "  app up, Liquibase created $TABLES tables"

echo "== 3. rotate admin credential (idempotent)"
"$ENV_DIR/scripts/bootstrap-admin.sh" >/dev/null
echo "PRISTINE: $APP_URL"
