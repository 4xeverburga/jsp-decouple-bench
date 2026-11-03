Read pom.xml, system.properties and LICENSE at the root of the checkout. Then create the file AGENT_PROBE.md at the root of the checkout, holding exactly these three lines:

PROBE_POM: the value inside the first <artifactId> element in pom.xml
PROBE_JAVA: the value of java.runtime.version in system.properties
PROBE_LICENSE: the first line of LICENSE

Nothing else in the file. Create no other file and change no existing one.
