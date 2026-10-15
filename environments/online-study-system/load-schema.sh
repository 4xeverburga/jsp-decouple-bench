#!/usr/bin/env bash
# One-shot schema loader: create the database and load the sample's tracked
# dump.  The dump targets MySQL 5.7 and utf8 — the client charset MUST be
# utf8 or the Chinese seed rows fail with "Data too long for column 'sex'".
set -euo pipefail

until mysql -h db -uroot -proot -e "SELECT 1" >/dev/null 2>&1; do sleep 2; done

mysql -h db -uroot -proot -e "CREATE DATABASE IF NOT EXISTS online_study_system CHARACTER SET utf8"
mysql -h db -uroot -proot --default-character-set=utf8 online_study_system < /sql/online_study_system.sql
echo "schema loaded"
