#!/bin/bash
# One-shot admin bootstrap. Runs in the postgres image, which has the client
# (the app container is busy serving), so it speaks to the database over the
# `data` network.
#
# OpenClinica seeds `root` with a published upstream password and a 2006
# password timestamp, which forces a reset-password page on first login. This
# rotates the password to the sample's credential — unsalted SHA-1, the
# encoder the app uses (`ShaPasswordEncoder`) — and stamps it today, so the
# seeded account is usable as-is. Idempotent: safe on every run.
set -euo pipefail

: "${OPENCLINICA_DB_HOST:?}" "${OPENCLINICA_DB_NAME:?}" \
  "${OPENCLINICA_DB_USER:?}" "${OPENCLINICA_DB_PASSWORD:?}" \
  "${OPENCLINICA_ADMIN_USER:?}" "${OPENCLINICA_ADMIN_PASSWORD:?}"

export PGPASSWORD="${OPENCLINICA_DB_PASSWORD}"

sql() {
  command psql -h "${OPENCLINICA_DB_HOST}" -U "${OPENCLINICA_DB_USER}" \
    -d "${OPENCLINICA_DB_NAME}" -v ON_ERROR_STOP=1 "$@"
}

# The schema is built by Liquibase while the app boots, and the port opens
# long before the tables exist: wait for the table this script touches.
echo "waiting for schema..."
ready=false
for _ in $(seq 1 180); do
  if sql -tAc "SELECT 1 FROM user_account LIMIT 1" >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 2
done
if [ "${ready}" != true ]; then
  echo "bootstrap failed: user_account never appeared" >&2
  exit 1
fi

SHA="$(printf '%s' "${OPENCLINICA_ADMIN_PASSWORD}" | sha1sum | cut -d' ' -f1)"

sql <<SQL
UPDATE user_account
   SET passwd = '${SHA}',
       passwd_timestamp = current_date,
       enabled = true
 WHERE user_name = '${OPENCLINICA_ADMIN_USER}';
SQL

COUNT="$(sql -tAc "SELECT count(*) FROM user_account \
WHERE user_name = '${OPENCLINICA_ADMIN_USER}' AND passwd = '${SHA}'")"
if [ "${COUNT}" != "1" ]; then
  echo "bootstrap failed: ${COUNT} account(s) match" >&2
  exit 1
fi
echo "admin bootstrap done (${OPENCLINICA_ADMIN_USER} rotated)"
