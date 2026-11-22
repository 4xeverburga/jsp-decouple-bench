# bench_controls — how strong are the cases?

The bench grades an agent by replaying end-to-end cases against the tree
it left: a browser flow plus a before/after delta of the database rows
(`functional_parity`). A verdict is only as good as those cases. A case
that never exercises a handler cannot notice that the agent broke it, and
a pass on it says nothing.

This package holds the code that measures the cases themselves. None of
it takes part in a solve or a score. It runs out of band, on the pinned
tree, and writes only under `out/coverage/`.

## What is measured

| # | metric | question it answers | source |
|---|---|---|---|
| 1 | **handler coverage** | does some case drive every handler of the target controller, and is every exception justified? | the manifest's `scope.covers` claim, checked against the controller's source and against execution |
| 2 | **line / branch coverage** | how much of the controller does each case's flow actually execute? | a JaCoCo agent attached to the app's JVM, one `.exec` per case |

Mutation testing (metric 3, "would the case fail if this line were
wrong?") is the next step and is not here yet.

### 1. Handler coverage

A manifest declares what its cases are meant to cover:

```json
"scope": {
  "cases": ["vote-flow__upvote-increments-count", "..."],
  "covers": {
    "controller": "org.mamute.controllers.VoteController",
    "handlers":   {"voteUp": "vote-flow__upvote-increments-count"},
    "not_driven": {"activate": "why no flow can reach it here"}
  }
}
```

The handler list is not taken from the claim. It is read from the
controller's source in the pinned tree: its `public` and `protected`
instance methods, minus constructors and bean accessors
(`get*`/`set*`/`is*`). Each handler then gets one status:

| status | meaning |
|---|---|
| `verified` | claimed by a case, and that case executed it |
| `NOT EXECUTED` | claimed by a case that never ran it — the claim is wrong |
| `not driven (excused)` | listed in `not_driven`, with its reason |
| `executed, unclaimed` | some case ran it but the claim does not say so (often an internal helper that is `public`) |
| `GAP` | nothing claims it and nothing ran it: a case still to write |

### 2. Line and branch coverage

`main.py coverage` cuts the pin and starts one stack per case, as scoring
does, so each measurement is that case alone on a pristine database. For
those stacks only, a compose override:

- adds `-javaagent:jacocoagent.jar=output=tcpserver,...` to the variable
  the sample already uses to load its OpenTelemetry agent (`MAVEN_OPTS`,
  `CATALINA_OPTS`), so the agent lands in the JVM that hosts the app;
- instruments only the app's own packages (`code_packages` in
  `seeds/samples.json`);
- mounts the JaCoCo jars read-only.

After the flow, the dump and the XML report run inside the app's
container, with the JDK and the compiled classes the image already has.
No Java is needed on the host. The classes are found from the
controller's own `.class` file, because samples compile to different
places (`target/classes`, or `WEB-INF/classes`).

Across several cases, lines are a true union. Branches are a per-line
maximum, which is a lower bound: separating two cases' branches on one
line needs their merged probes, and each stack is gone by then.

## Running it

```bash
BENCH_CHECKOUT=$PWD/../jsp-decouple-bench-samples/mamute \
  uv run python main.py coverage --manifest 3
```

`--case <id>` (repeatable) limits it to some of the manifest's cases.
It writes to `out/coverage/<manifest name>/`:

| file | what it holds |
|---|---|
| `report.md` | both tables, for reading |
| `report.json` | the same, for analysis |
| `<case>.exec`, `<case>.xml` | the raw JaCoCo data of each case |
| `<case>.compose.yaml` | the override that stack ran with |

A manifest without `scope.covers` is refused: there is no controller to
measure against.

## Configuration

The JaCoCo version and the sha256 of its two jars are parameters in
`bench.env` (`JACOCO_VERSION`, `JACOCO_AGENT_SHA256`, `JACOCO_CLI_SHA256`).
The jars are fetched from Maven Central once, checked, and kept in
`out/tools/`. Everything else is in `settings.py`, under "code coverage":
the output and tools directories, the repository the jars come from, the
agent's address, port and mount point, the dump directory inside the
container, the image workdir the classes are searched under, and the
OpenTelemetry flag that marks the JVM-options variable to extend.

## Code

| file | role |
|---|---|
| `coverage.py` | fetch the agent, write the override, play a case, parse the XML, cross it with the claim, write the report |

It reuses the harness rather than copying it: `src.bench.stack.running`
(which takes the override as an extra compose file),
`src.bench.scorers.functional_parity.cases.drive` (the same flow runner
the scorer uses) and the CLI's pin-cutting (`src/bench/cli.py`,
`_pinned`).
