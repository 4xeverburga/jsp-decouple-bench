#!/bin/bash
# One-shot admin bootstrap (runs in the mysql:5.7 image, which has the mysql
# client; the app container is busy running the app).
#
# Rotates the first-boot seeded moderator (moderator@mamuteqa.org, random
# md5 password) to the .env admin credentials.  Idempotent — safe on every
# run; runs after the app is healthy, so the schema + seed exist.
set -euo pipefail
: "${MAMUTE_ADMIN_USER:?}" "${MAMUTE_ADMIN_PASSWORD:?}"

# NOTE: a single quote in MAMUTE_ADMIN_PASSWORD would break this SQL — keep
# the password alphanumeric.
mysql -h db -uroot mamute_development <<SQL
SET @admin = '${MAMUTE_ADMIN_USER}';
SET @pass  = '${MAMUTE_ADMIN_PASSWORD}';
UPDATE LoginMethod lm JOIN Users u ON u.id = lm.user_id
   SET lm.serviceEmail = @admin,
       u.email         = @admin,
       lm.token        = SHA2(CONCAT(@pass, 'sadifhasdu34hqo9ihadfsoivuhaewuihfasiuasiufhifaew'), 256)
 WHERE lm.serviceEmail = 'moderator@mamuteqa.org';
SELECT COUNT(*) AS bootstrap_ok FROM LoginMethod WHERE serviceEmail = @admin;
SQL
echo "admin bootstrap done (seeded moderator rotated to .env credentials)"
