# JSP-Decouple-Bench

A falsifiable benchmark for **decoupling legacy JSP frontends from their
backends with REST APIs**. An agent is graded on behaviour parity against
frozen golden baselines — not on code style, and not on the legacy test
suite.

First benchmark in its category. Companion to (and filling the gap left by)
[MigrationBench](https://github.com/amazon-science/MigrationBench), which
covers Java version upgrades; this covers framework / view-layer decoupling.

## The task

Given a legacy JSP web app at a pinned commit and one feature boundary
("the vote flow"), decouple it: RESTify the controllers, remove the
server-rendered views for that flow, keep behaviour parity.

**There is no edit whitelist.** The agent may modify anything inside the
sample checkout — shared tags, interceptors, config, other pages. What is
bounded is the **verification scope**: the cases the run is graded against.

## The two commands

```bash
make db-init                                                  # build bench.db from schema + seeds

make task MANIFEST_ID=3 SAMPLE_LOCATION=../mamute HARNESS=claude-code   # -> run_id
make gate GATE_ID=functional_parity RUN_ID=<run_id>                     # -> value
```

`HARNESS` picks the agent adapter: `pristine` (no agent — the self-check),
`command` (any CLI, prompt on stdin), or the `claude-code` / `opencode` /
`pi` presets. `HARNESS_CMD='...'` overrides the command line.

**The agent never sees this repository, and never learns it is being
evaluated.** It gets a checkout and a one-paragraph work order — the
manifest prompt verbatim, with no routes, case names, goldens or
benchmark vocabulary. `harness.ports.HarnessTask` holds only `prompt` and
`cwd`, so that is structural rather than a convention. See `AGENTS.md`
for the supervisor's obligations.

`SAMPLE_LOCATION` is only *where the sample checkout lives on this
filesystem*. Provenance comes from `SAMPLE.commit_sha`: the runner checks
the worktree out to that commit and **refuses to run on a dirty tree**.

Inspection:

```bash
make samples      # registry: samples, pinned commits, entrypoints
make manifests    # registry: manifests, case counts, adapter bindings
make runs         # registry: runs
```

## Gates

Gates are independent and unordered — there is no composite score. More
will be added; RL environments consume them individually.

| Gate | Measures | Direction |
|---|---|---|
| `functional_parity` | Replays each case's Playwright flow and compares its DB delta and flow artifacts with the frozen golden. Logs every case to `out/runs/<run_id>/cases/<case>.json`. `value = passed / total` | maximize, threshold 1.0 |
| `network_isolation` | The running stack keeps the shape the sample declares: no host network, no undeclared networks, no undeclared published ports | maximize, threshold 1.0 |
| `trace_similarity` | **Pending.** Intended: compare captured OTel traces with an oracle (possibly an LLM) to catch calls that violate the new decomposition. Emits `verdict: "pending"`, `value: null` until an oracle is configured | maximize |

Every evaluation writes `out/runs/<run_id>/gates/<gate_id>.json`, recording
the `value`, the `verdict`, and the threshold/direction that were applied:

```json
{"gate_id": "functional_parity", "gate_version": 1, "run_id": "3f2c…",
 "value": 1.0, "verdict": "pass", "threshold": 1.0, "direction": "maximize",
 "duration_s": 812.4, "details": [{"case": "vote-flow__upvote-…", "verdict": "pass"}]}
```

`verdict` ∈ `pass | fail | error | pending`. Exit codes: 0 / 1 / 2 / 3.

## How an agent is scored

1. The runner prepares a run from a manifest (prompt + adapter bindings +
   case scope) and prints a `run_id`.
2. The agent works in the sample checkout at the pinned commit.
3. Gates are evaluated against that checkout and write one JSON each.
   A decoupled run passes `functional_parity` **and** `network_isolation`;
   `trace_similarity` stays `pending` until it is specified.

A tree that does not build cannot pass `functional_parity`: the stack never
becomes healthy and the gate reports `error` (never a fabricated score).

## Layout

```
bench.db                  # git-tracked registry: samples, technologies, manifests, runs, gates
schema.sql                # its DDL (PRAGMA user_version guards drift)
main.py  config.py        # the CLI and every tunable
specs/                    # er.md, modules.md, behavior.md — the contract
seeds/                    # rows loaded by `make db-init`
src/tasks/                # one task implementation (scope comes from the manifest)
src/gates/                # functional_parity (+ its case corpus), network_isolation, trace_similarity
src/env/                  # environment adapters: start, drive, inspect a sample
src/harness/              # agent harnesses: pristine, command, claude-code, opencode, pi
out/runs/<run_id>/        # task.json, diff.patch, cases/*.json, gates/*.json (gitignored)
```

Samples carry their own environment: **`compose.yaml` lives in the sample
repo**, not here, and is part of the pinned commit. The harness exports
`BENCH_HTTP_PORT` / `BENCH_DB_PORT` per run and gives each run its own
compose project (`bench-<run_id>`), so concurrent runs never collide on
files or ports.

Adapters are chosen **by technology**, not by sample — `mysql@1` serves
every MySQL sample. Which adapter a run uses is data: the manifest's
`bindings_json`. Available: `compose@1`, `playwright@1`, `mysql@1`,
`postgres@1`, `h2@1`, `shell@1`.

## Samples

| Sample | DB | Stack | Entrypoint |
|---|---|---|---|
| `mamute` | MySQL | VRaptor 4, 49 JSPs, 78 tag files | `compose.yaml` |
| `online-study-system` | MySQL | Spring MVC 4.3, Shiro, JSP/JSTL | `compose.yaml` |
| `openclinica` | PostgreSQL | Spring MVC 3.2, 807 JSPs (bounded flow only) | not yet authored |

17 behaviour cases, 13 manifests.

### Adding or re-pinning a sample

```bash
cp -r <env assets> ../<sample>/          # compose.yaml, Dockerfile, .env(.example)
git -C ../<sample> add -A && git -C ../<sample> commit -m "..."
make pin SAMPLE=<slug> SAMPLE_LOCATION=../<sample>   # pin to that commit
make case-capture SAMPLE=<slug> CASE=<case> SAMPLE_LOCATION=../<sample>
```

`expect.json` is always **generated** by `case-capture` from the pristine
tree — never hand-written.

## Status

v1.0 — the rewrite is complete: registry, both verbs, three gates, 17 cases
and 13 manifests migrated. Not yet done: the trace adapter + oracle
(`trace_similarity` stays `pending`), and `compose.yaml` for `openclinica`.
See `ROADMAP.md` for decisions of record, `AGENTS.md` for the agent
contract, and `specs/` for the normative definitions.
