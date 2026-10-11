#!/usr/bin/env bash
# From-scratch admin-credential lifecycle test for OpenClinica.
#
# Proves the full chain on a FRESH database:
#   1. fresh DB  -> Liquibase seeds root/12345678 (upstream seed) and it
#      authenticates (forcing the expired-password reset page)
#   2. bootstrap -> scripts/bootstrap-admin.sh rotates to the GITIGNORED
#      .env password
#   3. seed password 12345678 is REJECTED
#   4. gitignored password logs in and reaches the MainMenu
#
# WARNING: DESTRUCTIVE — drops and recreates the 'openclinica' database
# and restarts Tomcat. Opt-in only: after credential/bootstrap changes,
# or to reset a polluted DB. Anything created in the app is lost.
# Regular e2e tests must NEVER call this — they use setup-e2e.sh.
#
# Usage: ./scripts/test-admin-from-scratch.sh
set -euo pipefail

ENV_DIR=$(cd "$(dirname "$0")/.." && pwd)
source "$ENV_DIR/.env"

: "${OPENCLINICA_ADMIN_USER:=root}"
: "${OPENCLINICA_HTTP_PORT:=8089}"
APP_URL=http://localhost:$OPENCLINICA_HTTP_PORT/OpenClinica
TC=${OPENCLINICA_TOMCAT_HOME:-/home/ever/tools/apache-tomcat-oc}
JDK8=${OPENCLINICA_JDK8:-/usr/lib/jvm/jdk-8.0.202-oracle-x64}
SEED_PW=12345678
JAR=$(mktemp)

pass() { echo "  PASS: $1"; }
fail() { echo "  FAIL: $1"; exit 1; }

post_login() { # $1=password -> prints the page the login POST lands on
  rm -f "$JAR"
  curl -s -L -c "$JAR" --data "j_username=$OPENCLINICA_ADMIN_USER&j_password=$1" \
    "$APP_URL/j_spring_security_check" --max-time 30
}

# authenticated = NOT bounced back to the login form (either the welcome
# dashboard or the forced reset-password page counts as authenticated)
auth_ok() { # $1=password
  ! post_login "$1" | grep -q 'name="j_username"'
}

# full dashboard = authenticated AND password not expired. NOTE: the
# welcome text is a flash message rendered only on the page right after
# login, so it must be checked on the POST's landing page, not on a
# later MainMenu GET.
menu_ok() { # $1=password
  post_login "$1" | grep -q 'Welcome to OpenClinica, Root User'
}

echo "== 0. preconditions"
[[ -f "$ENV_DIR/.env" ]] || { echo "  FAIL: .env missing (cp from .env.example)"; exit 1; }
[[ -n "${OPENCLINICA_ADMIN_PASSWORD:-}" && "$OPENCLINICA_ADMIN_PASSWORD" != "CHANGE_ME" ]] || {
  echo "  FAIL: set OPENCLINICA_ADMIN_PASSWORD in .env"; exit 1; }
podman ps --format '{{.Names}}' | grep -q '^openclinica-pg$' || { echo "  FAIL: openclinica-pg container not running"; exit 1; }
pass "container up, gitignored credentials present"

echo "== 1. stop Tomcat, drop + recreate the database (fresh seed)"
"$TC/bin/catalina.sh" stop -force >/dev/null 2>&1 || true
sleep 3
podman exec openclinica-pg psql -U clinica -d postgres -v ON_ERROR_STOP=1 -q \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='openclinica' AND pid <> pg_backend_pid();" \
  -c "DROP DATABASE IF EXISTS openclinica;" \
  -c "CREATE DATABASE openclinica OWNER clinica;"
pass "tomcat stopped, database dropped and recreated empty"

echo "== 2. start Tomcat -> Liquibase re-seeds schema"
JAVA_HOME="$JDK8" CATALINA_HOME="$TC" CATALINA_BASE="$TC" "$TC/bin/catalina.sh" start >/dev/null
for i in $(seq 1 60); do
  CODE=$(curl -s -o /dev/null -w '%{http_code}' "$APP_URL/pages/login/login" --max-time 5 || true)
  TABLES=$(podman exec openclinica-pg psql -U clinica -d openclinica -t -A -c \
    "select count(*) from information_schema.tables where table_schema='public';" 2>/dev/null || echo 0)
  if [[ "$CODE" == "200" && "$TABLES" -ge 100 ]]; then break; fi
  sleep 3
done
[[ "$CODE" == "200" && "$TABLES" -ge 100 ]] || fail "app/schema not ready after restart (code=$CODE tables=$TABLES)"
pass "app up, Liquibase created $TABLES tables"

echo "== 3. upstream seed credential authenticates on a fresh DB"
auth_ok "$SEED_PW" || fail "seed password 12345678 did not authenticate on fresh DB"
post_login "$SEED_PW" | grep -q 'mustChangePwd' || fail "fresh seed did not force the expired-password reset"
pass "seed root/12345678 authenticates (and correctly forces a reset: seed timestamp is 2006)"

echo "== 4. bootstrap rotates to the gitignored credential"
"$ENV_DIR/scripts/bootstrap-admin.sh" >/dev/null
pass "bootstrap-admin.sh ran"

echo "== 5. seed password is now rejected"
auth_ok "$SEED_PW" && fail "seed password 12345678 STILL authenticates after rotation"
pass "seed password rejected (bounced back to login form)"

echo "== 6. gitignored credential logs in"
menu_ok "$OPENCLINICA_ADMIN_PASSWORD" || fail "gitignored admin password did not log in"
pass "gitignored admin password logs in"

echo
echo "ALL PASS: admin credential lifecycle verified from scratch."
rm -f "$JAR"
