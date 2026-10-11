#!/bin/bash
# Mamute sample app entrypoint: point hibernate at the compose db, write
# development.properties from the example, start the app on embedded Jetty.
# (The admin-credential bootstrap is a separate one-shot compose service —
# it needs the mysql client, which lives in the mysql:5.7 image.)
set -euo pipefail

cd /workspace

# 1. The dev hibernate config hardcodes localhost; rewrite for the compose db.
#    TWO copies exist: the source tree AND the classpath copy the pom placed
#    in WEB-INF/classes at compile time — Hibernate loads the classpath one.
sed -i 's#jdbc:mysql://localhost/#jdbc:mysql://db:3306/#' \
  src/main/resources/development/hibernate.cfg.xml \
  src/main/webapp/WEB-INF/classes/development/hibernate.cfg.xml

# 2. Wait for MySQL (schema is created by the app itself on first boot).
echo "waiting for db..."
for i in $(seq 1 120); do
  (echo > /dev/tcp/db/3306) 2>/dev/null && break
  sleep 1
done

# 3. host = the externally-visible URL (VRaptor builds absolute redirect and
#    OAuth-callback URLs from it).  In-container port is always 8080.
HOST_URL="${MAMUTE_PUBLIC_URL:-http://localhost:8090}"
sed -i "s#^host = .*#host = ${HOST_URL}#" \
  src/main/resources/development.properties

# 4. Start the app in the foreground (embedded Jetty 8; `not-grunt` = assets
#    already built into the image).
exec mvn -B exec:java \
  -Dexec.mainClass=br.com.caelum.vraptor.server.Main \
  -Dexec.args="not-grunt" \
  -Dserver.port=8080
