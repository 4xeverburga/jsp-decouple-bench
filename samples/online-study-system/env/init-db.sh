#!/bin/bash
# Loads the tree's schema and seed rows, once, while MySQL initialises the
# volume (`docker-entrypoint-initdb.d`). The `db` service stays unhealthy until
# the server is up for real, so `front` starts on a seeded database.
#
# The dump is UTF-8 and its `sex` column is one character wide: a client that
# connects as latin1 fails it with "Data too long for column 'sex'", which is
# why the charset is set here rather than left to the client's default.
set -euo pipefail

: "${MYSQL_ROOT_PASSWORD:?}" "${MYSQL_DATABASE:?}"

mysql --default-character-set=utf8 -uroot -p"${MYSQL_ROOT_PASSWORD}" \
  --database="${MYSQL_DATABASE}" < /schema.sql
