#!/bin/bash
# Loads the tree's schema and seed rows, once, while MySQL initialises the
# volume (`docker-entrypoint-initdb.d`). The `db` service stays unhealthy until
# the server is up for real, so `front` starts on a seeded database.
#
# The dump creates and selects `bookshopdb` itself. Its strings are
# Vietnamese UTF-8, so the client charset is set here, not left to defaults.
set -euo pipefail

: "${MYSQL_ROOT_PASSWORD:?}"

mysql --default-character-set=utf8mb4 -uroot -p"${MYSQL_ROOT_PASSWORD}" \
  < /schema.sql
