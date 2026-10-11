#!/usr/bin/env bash
# Idempotent setup for running OpenClinica e2e tests.
#
# Brings the environment to a known "bootstrapped app" state WITHOUT
# destroying anything:
#   - PostgreSQL container: started if stopped
#   - database: created ONLY if missing (never dropped)
#   - Tomcat: started if not running (Liquibase seeds a fresh schema)
#   - admin credential: bootstrap-admin.sh is idempotent — safe every run
#   - .env: auto-generated (random password) if missing, so a fresh
#     checkout converges with no manual step
#
# Usage: ./scripts/setup-e2e.sh
set -euo pipefail

ENV_DIR=$(cd "$(dirname "$0")/.." && pwd)
source "$ENV_DIR/.env" 2>/dev/null || true

: "${OPENCLINICA_HTTP_PORT:=8089}"
APP_URL=http://localhost:$OPENCLINICA_HTTP_PORT/OpenClinica
TC=${OPENCLINICA_TOMCAT_HOME:-/home/ever/tools/apache-tomcat-oc}
JDK8=${OPENCLINICA_JDK8:-/usr/lib/jvm/jdk-8.0.202-oracle-x64}

db_exists() {
  podman exec openclinica-pg psql -U clinica -d postgres -t -A -c \
    "SELECT 1 FROM pg_database WHERE datname='openclinica';" 2>/dev/null | grep -q 1
}
table_count() {
  podman exec openclinica-pg psql -U clinica -d openclinica -t -A -c \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null || echo 0
}
app_up() {
  [[ "$(curl -s -o /dev/null -w '%{http_code}' "$APP_URL/pages/login/login" --max-time 5 || true)" == "200" ]]
}

echo "== 1. PostgreSQL container"
if podman ps --format '{{.Names}}' | grep -q '^openclinica-pg$'; then
  echo "  already running"
else
  if podman ps -a --format '{{.Names}}' | grep -q '^openclinica-pg$'; then
    podman start openclinica-pg >/dev/null
  else
    podman run -d --name openclinica-pg \
      -e POSTGRES_USER=clinica -e POSTGRES_PASSWORD=clinica -e POSTGRES_DB=openclinica \
      -p 5433:5432 docker.io/library/postgres:9.6 >/dev/null
  fi
  sleep 4
  echo "  started"
fi

echo "== 2. database (create only if missing — never drop)"
if db_exists; then
  echo "  exists ($(table_count) tables)"
else
  podman exec openclinica-pg psql -U clinica -d postgres -v ON_ERROR_STOP=1 -q \
    -c "CREATE DATABASE openclinica OWNER clinica;"
  echo "  created empty"
fi

echo "== 3. Tomcat (start only if not running)"
if app_up; then
  echo "  already up"
else
  JAVA_HOME="$JDK8" CATALINA_HOME="$TC" CATALINA_BASE="$TC" "$TC/bin/catalina.sh" start >/dev/null
  for i in $(seq 1 60); do
    CODE=$(curl -s -o /dev/null -w '%{http_code}' "$APP_URL/pages/login/login" --max-time 5 || true)
    TABLES=$(table_count)
    if [[ "$CODE" == "200" && "$TABLES" -ge 100 ]]; then break; fi
    sleep 3
  done
  [[ "$CODE" == "200" && "$TABLES" -ge 100 ]] || { echo "  FAIL: app not ready (code=$CODE tables=$TABLES)"; exit 1; }
  echo "  started (Liquibase ready, $TABLES tables)"
fi

echo "== 4. admin credential (gitignored, idempotent)"
if [[ ! -f "$ENV_DIR/.env" ]]; then
  PW=$(openssl rand -base64 12 | tr -d '/+=' | cut -c1-14)
  printf 'OPENCLINICA_ADMIN_USER=root\nOPENCLINICA_ADMIN_PASSWORD=%s\nOPENCLINICA_HTTP_PORT=%s\n' \
    "$PW" "$OPENCLINICA_HTTP_PORT" > "$ENV_DIR/.env"
  echo "  generated .env (read it for the password)"
else
  echo "  .env present"
fi
"$ENV_DIR/scripts/bootstrap-admin.sh" >/dev/null
echo "  bootstrap applied (idempotent)"

echo "== 5. verify admin login"
source "$ENV_DIR/.env"
JAR=$(mktemp); trap 'rm -f "$JAR"' EXIT
BODY=$(curl -s -L -c "$JAR" --data "j_username=$OPENCLINICA_ADMIN_USER&j_password=$OPENCLINICA_ADMIN_PASSWORD" \
  "$APP_URL/j_spring_security_check" --max-time 30)
echo "$BODY" | grep -q 'Welcome to OpenClinica, Root User' || { echo "  FAIL: admin login rejected"; exit 1; }
echo "  admin login OK"

echo
echo "READY: app at $APP_URL — e2e tests read the password from environments/openclinica/.env."
