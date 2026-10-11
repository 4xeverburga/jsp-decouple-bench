#!/usr/bin/env bash
# Rotate the seeded OpenClinica 'root' admin password using the password
# from this sample's TRACKED .env (synthetic bench credential — see
# .gitignore). Idempotent — run after every fresh
# database (a fresh DB re-seeds root/12345678 from upstream's tracked
# Liquibase changelog; that seed is public upstream knowledge, so the
# bench credential is applied here).
#
# Usage: ./scripts/bootstrap-admin.sh
set -euo pipefail

ENV_DIR=$(cd "$(dirname "$0")/.." && pwd)
source "$ENV_DIR/.env"

: "${OPENCLINICA_ADMIN_USER:=root}"
[[ -n "${OPENCLINICA_ADMIN_PASSWORD:-}" && "$OPENCLINICA_ADMIN_PASSWORD" != "CHANGE_ME" ]] || {
  echo "ERROR: set OPENCLINICA_ADMIN_PASSWORD in $ENV_DIR/.env"; exit 1; }

# The app's current encoder is Spring's ShaPasswordEncoder: unsalted,
# lowercase hex SHA-1. Match it exactly.
HASH=$(printf '%s' "$OPENCLINICA_ADMIN_PASSWORD" | sha1sum | cut -d' ' -f1)

podman exec -i openclinica-pg psql -U clinica -d openclinica -v ON_ERROR_STOP=1 <<SQL
  UPDATE user_account
     SET passwd = '$HASH',
         passwd_timestamp = current_date
   WHERE user_name = '$OPENCLINICA_ADMIN_USER';
SQL

echo "OK: $OPENCLINICA_ADMIN_USER password rotated (SHA-1), expiry reset to today."
echo "The seed password 12345678 no longer works."
