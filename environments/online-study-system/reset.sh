#!/usr/bin/env bash
# Reset the online-study-system stack to pristine seed state (for golden-delta
# capture and coverage runs — NOT part of the e2e test contract, which forbids
# DB drops inside tests).
#
# compose v5 `up --wait` exits 1 when the one-shot `schema` service exits (0),
# so we start detached and poll readiness ourselves: HTTP 200 on login.jsp.
set -euo pipefail

ENV_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1090
source "$ENV_DIR/.env"
APP_URL="http://localhost:${OSS_HTTP_PORT:-8091}/Examination_System"

echo "== 1. tear the stack down (volume included)"
docker compose -f "$ENV_DIR/compose.yml" down -v --remove-orphans

echo "== 2. rebuild the app image and start detached (schema one-shot runs before the app)"
docker compose -f "$ENV_DIR/compose.yml" build app
docker compose -f "$ENV_DIR/compose.yml" up -d

echo "== 3. poll readiness"
for _ in $(seq 1 90); do
  CODE=$(curl -s -o /dev/null -w '%{http_code}' "$APP_URL/login.jsp" --max-time 5 || true)
  if [[ "$CODE" == "200" ]]; then
    echo "app is up: $APP_URL"
    exit 0
  fi
  sleep 2
done
echo "app did not become ready — check: docker compose -f $ENV_DIR/compose.yml logs app" >&2
exit 1
