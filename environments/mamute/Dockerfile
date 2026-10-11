# Mamute bench sample image — JDK 8 + Maven, run via embedded Jetty 8
# (br.com.caelum.vraptor.server.Main), DB = MySQL 5.7 (compose `db` service).
#
# Build context is the mamute repo (see compose.yml); this Dockerfile lives in
# the bench repo so the sample stays untouched.
#
# NOTE: NO `apt-get install` here — the base (Debian bullseye) is EOL and its
# security pool 404s. Node for the grunt build comes from the official
# tarball; curl/wget are already in the base image; the mysql client lives in
# the one-shot `bootstrap` compose service (mysql:5.7 image) instead.
FROM maven:3.8.6-openjdk-8

# Node 16: grunt 0.4-era toolchain.  Static tarball from nodejs.org.
RUN wget -qO- https://nodejs.org/dist/v16.20.2/node-v16.20.2-linux-x64.tar.gz \
      | tar -xz -C /opt
ENV PATH=/opt/node-v16.20.2-linux-x64/bin:${PATH}

WORKDIR /workspace

# Dependency-cache layer (local-repo holds vendored jars referenced by the pom)
COPY pom.xml ./
COPY local-repo ./local-repo
RUN mvn -B -q dependency:go-offline || true

COPY src ./src

# Compile — the pom sets output to src/main/webapp/WEB-INF/classes/
RUN mvn -B -q compile

# Generate development.properties from the tracked example BEFORE any other
# layer: the host copy is gitignored (holds OAuth secrets) and may be in the
# build context — never bake it into the image.
RUN rm -f src/main/resources/development.properties \
 && cp src/main/resources/development.properties.example \
       src/main/resources/development.properties

# Web assets: `grunt build` deletes src/main/webapp/assets/ and rewrites
# templates to hashed refs (documented mamute behavior; inside the image this
# is harmless).  Generates webapp/{css,js,imgs,font}.
COPY package.json Gruntfile.js ./
RUN npm install --no-audit --no-fund --loglevel=error \
 && ./node_modules/grunt-cli/bin/grunt build

# entrypoint.sh is bind-mounted read-only at runtime by compose.yml — it is
# bench infra and must not be baked into (or drift inside) the image.

# Must run on JDK 8 (Java 7 source/target; machine JDKs differ).
# The base image's own JAVA_HOME (/usr/local/openjdk-8) is already correct —
# just make it explicit for the runtime entrypoint.
ENV JAVA_HOME=/usr/local/openjdk-8
ENTRYPOINT ["bash", "./entrypoint.sh"]
