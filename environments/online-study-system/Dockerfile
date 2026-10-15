# Online Study System bench sample image — JDK 8 + Maven build, runtime is
# Tomcat 9 (javax.servlet stack; Tomcat 10+ jakarta will NOT work).
#
# Build context is the Online_Study_System repo (see compose.yml); this
# Dockerfile lives in the bench repo so the sample stays untouched.
#
# The sample's mysql.properties points at localhost:3306 (the manual-runbook
# setup).  Inside the compose stack the DB is the `db` service — rewrite the
# host in the image only (same pattern as mamute's development.properties).
FROM maven:3.8.6-openjdk-8 AS build

WORKDIR /workspace

# Dependency-cache layer
COPY pom.xml ./
RUN mvn -B -q dependency:go-offline || true

COPY src ./src
RUN mvn -B -q package -DskipTests

FROM tomcat:9-jdk8-temurin

# Point the app at the compose `db` service (host rewrite only — no other
# property changes; useSSL stays as upstream wrote it).
COPY --from=build /workspace/target/Examination_System.war \
     /usr/local/tomcat/webapps/Examination_System.war
# useSSL=false: the image's JDK 8 build disables the legacy TLS protocols
# MySQL 5.7 negotiates, so the upstream useSSL=true URL cannot connect here
# (SSLHandshakeException: No appropriate protocol).  Same image-only rewrite
# pattern as the host change above.
RUN cd /tmp && mkdir oss && cd oss \
 && /opt/java/openjdk/bin/jar xf /usr/local/tomcat/webapps/Examination_System.war \
 && sed -i -e 's|jdbc:mysql://localhost:3306|jdbc:mysql://db:3306|' \
           -e 's|useSSL=true|useSSL=false|' \
      WEB-INF/classes/mysql.properties \
 && rm -f /usr/local/tomcat/webapps/Examination_System.war \
 && mv /tmp/oss /usr/local/tomcat/webapps/Examination_System

# Must run on JDK 8 (the base image's own java is already 8 — explicit for clarity).
ENV JAVA_HOME=/opt/java/openjdk
