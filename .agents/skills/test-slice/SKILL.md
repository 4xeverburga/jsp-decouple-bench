---
name: test-slice
description: >
  Add a new behavior test slice to a sample in this benchmark: pick the
  behavior, author the e2e flow (spec.json + flow.py) and the db spec,
  capture the golden delta with scripts/capture_delta.py, prove
  determinism with a second run, and re-freeze the manifest. Use when
  asked to "add a test slice", "create a new behavior test", "author
  another flow for <sample>", "capture a golden delta", or "test
  another slice of <sample>".
---

# Test slice — add one behavior test to a sample

A **slice** is a task (feature boundary, e.g. `mamute/vote-flow`); a
**behavior test** is one observable behavior of that slice. One test =
one directory pair, named `<task>__<behavior>`, under the sample:

```
bench/e2e/<sample>/<task>__<behavior>/   spec.json + flow.py (+ images/, artifacts.json after capture)
bench/db/<sample>/<task>__<behavior>/    spec.json + expected_delta.json (captured, never hand-written)
```

## Procedure

### 1. Design the behavior (read the sample's source)

Trace the controller/route for the behavior in the sample repo
(`../<sample>/src`). Note: the exact route paths, the widget that
triggers it, karma/permission gates (and whether the seeded moderator
bypasses them), and which tables the DAO layer touches. Split
multi-behavior ideas into separate dirs — granularity makes verdicts
diagnosable.

### 2. Author the e2e test

Copy the structure from a sibling test dir of the same sample.

`spec.json` fields: `task`, `behavior`, `routes` (every URL the flow
hits), `locale: "en-US"`, `timezone_id: "UTC"`, `viewport`,
`auth`, `credentials: "env:<VARS>"`, `requires_db_reset: true`,
`artifacts` (what `run()` returns).

`flow.py` rules (all hard-won — violating any of these cost a debug
cycle):

- **Self-contained arrange**: sign up / create entities in-flow with
  deterministic fixed credentials; act with the seeded actor whose
  credentials come from `os.environ` only (the harness injects the
  sample `.env`). Never hardcode passwords, never rely on prior state.
- **Wait for submit navigations explicitly**:
  `with page.expect_navigation(wait_until="load"): page.click(...)` —
  `click` + `wait_for_load_state` races the redirect.
- **Wait for signals, never sleep**: `page.expect_response("**/route")`
  around the action click; `wait_for_load_state("networkidle")` after
  navigation; `wait_for_function` for DOM updates — and when building a
  JS predicate with `%` formatting, check the braces survive it (a
  missing `}` here once broke every vote wait).
- **Legacy widgets need UI driving**: select2 v3 inputs are hidden —
  click `.select2-container`, `fill(".select2-input", ...)`,
  `wait_for_selector(".select2-result-selectable")`, click the result.
  Filling the hidden input times out.
- **Snapshots**: normalize `page.content()` (strip `<script>/<style>`,
  collapse whitespace) before/after the act; return artifacts dict.

### 3. Author the db spec

Start from a sibling test's table list for the same flow, then let the
capture run correct it empirically (step 4 prints every changed table
outside the spec). Key columns come from `DESCRIBE <table>` — join
tables in mamute use `tags_id`/`watchers_id`, not `Tag_id`/`Watcher_id`.
Ignore every volatile column (all timestamps, counters not asserted on).
Exclude auth plumbing (e.g. `UserSession`) deliberately and say why in
`notes`.

### 4. Capture the golden delta

```bash
# pristine state is mandatory: ids must match across runs
docker compose -f environments/<sample>/compose.yml down -v
docker compose -f environments/<sample>/compose.yml up -d --wait
.venv/bin/python scripts/capture_delta.py <sample> <task>__<behavior>
```

`capture_delta.py` is sample-generic: base URL, DB access command and
table-list query live in `environments/<sample>/capture.env` (SQL travels
over stdin — no quoting pitfalls between mysql and psql). It imports the
test's own `flow.py` (single source of truth), runs it against the
pristine app, screenshots every step into the test dir's `images/`,
writes `artifacts.json`, and freezes the before/after dump diff as
`bench/db/<sample>/<test>/expected_delta.json`. Docker may need
`sg docker -c "..."` if the shell predates group membership.

If it prints `WARNING — changes outside the spec's table list`, fix the
db spec (add tables / ignore_columns) and re-capture. Never hand-edit
`expected_delta.json`.

### 5. Determinism gate (mandatory)

Reset the stack again and capture a second time; the two
`expected_delta.json` files must be byte-identical (`diff`). Ids are
stable because every fresh boot replays the same seed — if they differ,
the environment is not deterministic; stop and fix that first.

### 6. Freeze and commit

```bash
python3 bench/harness/manifest.py generate bench
python3 bench/harness/manifest.py verify bench/MANIFEST.sha256
```

Commit test dirs + manifest together. `bench/` is eval infrastructure:
anything under it is checksummed, and researchers trace every frozen
expectation through the test dir's `images/` and `artifacts.json`.

## Pitfalls that cost a debug cycle (learned on mamute + openclinica)

- **Pick the behavior direction that leaves a DB fingerprint.** mamute's
  unwatch only deletes a join-table row (the `Watcher` row persists —
  `Question.remove(Watcher)` mutates an in-memory list), so the before/
  after dump nets to zero and `db_state` carries no signal. Capture the
  *insert* direction instead, and document the quirk in the db spec's
  `notes`.
- **Forms that prefill volatile values break determinism.** openclinica's
  AddNewSubject prefills `enrollmentDate` with *today* — fill every date
  explicitly with a fixed value before submitting.
- **Legacy apps stall on keep-alive reuse** (openclinica intermittently
  hangs `goto`). Wrap navigation in a goto-with-one-retry helper instead
  of sleeping.
- **Never run a capture smoke test against a dirty stack "just to check
  the DB wiring"** — it overwrites the frozen `images/` of an existing
  test dir. If it happens: `git checkout -- <test dir>/images/`, delete
  untracked new shots, regenerate the manifest, and re-verify.
- **A partial flow still writes rows.** A killed capture leaves the DB
  dirty; always reset before the next capture, not just before the first.

## Measuring dynamic code coverage of the flows

`scripts/measure-coverage.sh <sample> <test>...` runs each flow against a
pristine stack with the JaCoCo agent injected and produces per-test plus
aggregate CSV/HTML reports under `coverage/<sample>/` (gitignored — never
under `bench/`). Knobs per sample live in `environments/<sample>/
coverage.env` (stack mode `compose` or `tomcat-local`, app URL, class and
source paths, agent port). JaCoCo jars are vendored in `tools/jacoco/`.

Hard-won rules baked into the tooling — do not simplify them away:

- **Use tcpserver mode + `jacococli dump`, never `output=file`.** The
  file is written on JVM shutdown, and the *next* JVM (post-restart)
  truncates it on boot with `append=false` — a race the harness loses.
- **One tcpserver port per sample** (`COVERAGE_AGENT_PORT`): two sample
  stacks up at once will fight over 6300 and the agent's premain failure
  kills the whole JVM (`FATAL ERROR ... processing of -javaagent failed`).
- **Never inherit the shell `JAVA_HOME`** (machine default is JDK 21;
  these apps are Java 7 on JDK 8). Pin it in every start command.
- **Write the agent config before the sample's reset script runs** and do
  not stop/start Tomcat again afterwards — a second restart races the
  dying JVM's agent socket (`Address already in use` on the agent port).
- **compose v5 `up --wait` exits 1 when a one-shot service exits (0)** —
  poll readiness yourself (HTTP 200 + every container healthy or
  `Exited (0)`) instead of trusting the exit code.

How to read the reports: the metric that matters is **which controllers/
DAOs each slice covers** (per-test CSV) and which stay at 0% in the
aggregate — 0% controllers are the prioritized backlog of next slices,
not a failure. Whole-app percentages are meaningless (JSPs/JS are not
Java; OAuth/Solr-style controllers are unreachable in the deterministic
environment).
