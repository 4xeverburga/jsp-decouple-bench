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

make task MANIFEST_ID=3 SAMPLE_SANDBOX=/abs/tmp/run-<id> \
          HARNESS=opencode-ds-flash-max \
          HARNESS_CMD='/opt/opencode run --auto --model opencode-go/deepseek-v4.1-flash#max "$$(cat)"'
make gate GATE_ID=functional_parity RUN_ID=<run_id>                     # -> value
```

There is one harness, and it is **the command you give it**: the prompt
arrives on stdin, so `opencode`, `claude`, `copilot`, the model and its
effort are argv, never code. `HARNESS_CMD` and `HARNESS` are both required
on every run — no agent command is kept in `.env`, so a stale one can never
outlive it. `HARNESS=<label>` selects nothing — it is the free text recorded
in `TASK_RUN.harness`, so name it after the model and effort
(`opencode-ds-flash-max`) when you intend to compare runs. The exact command
that ran is in `out/runs/<run_id>/harness.json` either way.

**Effort is the model's variant**: `--model provider/model#low|default|high|max`.
Without a `#variant` you silently get the CLI's own default, which is why a
run can look identical in the log while costing a fraction of the tokens.

A CLI that takes the prompt as an argument reads it with `"$(cat)"`. Passed
through `make` that must be written `"$$(cat)"`, because make otherwise
expands `$(cat)` as a missing make variable and hands the agent an empty
prompt.

**The agent never sees this repository, and never learns it is being
evaluated.** It gets a checkout and a one-paragraph work order — the
manifest prompt verbatim, with no routes, case names, goldens or
benchmark vocabulary. `harness.ports.HarnessTask` holds only `prompt` and
`cwd`, so that is structural rather than a convention. See `AGENTS.md`
for the supervisor's obligations.

### Isolation comes from the sandbox, not a wrapper

The agent runs as the supervisor's user, so `$HOME` and `/tmp` are as
reachable as the tree it was handed — two runs were scored against the
goldens that way, one through the sample's own git ancestry and one through
a replay harness left in the supervisor's `/tmp` scratch.

That belongs to whatever provisions the stack. In the ported bench
(`inspect_port/`) Inspect boots the compose project itself and the agent
runs inside that sandbox, so the agent never needs the docker socket and
there is no wrapper to maintain: the hand-rolled bwrap script this section
used to document is deleted rather than kept in parallel.

`SAMPLE_SANDBOX` is the folder allocated to **one** run (absolute path,
absent or empty). The bench puts that run's only checkout there and refuses
a folder that already holds something: nothing sits beside the agent's tree,
because a sibling is somewhere to look for the answer. The commit comes
from the registry (`SAMPLE.source` + `SAMPLE.commit_sha`) through a bare
mirror at `out/cache/<slug>.git`, so a run needs neither network nor
credentials once the mirror has the pin. The clone is then scrubbed —
remote, branches, tags and reflog deleted — and the agent sees a checkout,
not a repository history.

Inspection:

```bash
make samples      # registry: samples, pinned commits, entrypoints
make manifests    # registry: manifests, case counts, adapter bindings
make runs         # registry: runs
```

## Watching a run

Both commands report progress on **stderr** while they work, so a run that
is still going never looks like a hung terminal; stdout carries only the
result (a `run_id`, or a gate's JSON). The agent's own output is streamed
line by line as it arrives, and mirrored into
`out/runs/<run_id>/harness.log`:

```
01:17:12 INFO  bench.main     run acc83c12 — mamute/answer-flow v1 (decouple_slice) harness='opencode'
01:17:12 INFO  bench.task     pinning mamute to ea25617cd8
01:17:12 INFO  bench.harness  cwd ../mamute (timeout 3600s)
01:17:20 INFO  bench.harness  › reading AnswerController.java
01:17:29 INFO  bench.harness  still running (17s elapsed)
02:03:41 INFO  bench.harness  harness 'opencode' exited 0 in 2789.0s
```

A stack that is still starting reports its container statuses every
`BENCH_HEARTBEAT_S`, and so does a long-running child, so silence always
means "nothing is happening", never "nothing to see". `BENCH_LOG_LEVEL=DEBUG`
adds the quiet calls (`compose ps|config`, db dumps, `exec`). Both keys are
required, like every other tunable in `.env`.

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

## Runs and gates

1. The runner prepares a run from a manifest (prompt + adapter bindings +
   case scope), the harness works in the sample checkout at the pinned
   commit, and the run is **finished** when the harness returns. A run has
   no pass/fail and no pending state.
2. Gates are independent measurements of a finished run's tree; each writes
   one JSON. Which gates to run, how to combine them and what counts as
   "good" is up to whoever consumes the bench.

A tree that does not build cannot pass `functional_parity`: the stack never
becomes healthy and the gate reports `error` (never a fabricated score).

## Layout

```
bench.db                  # git-tracked registry: samples, technologies, manifests, runs, gates
schema.sql                # its DDL (PRAGMA user_version guards drift)
main.py  config.py        # the CLI and every tunable
src/log.py   src/run/     # progress logging, run-scoped primitives (incl. the streaming runner)
specs/                    # er.md, modules.md, behavior.md — the contract
seeds/                    # rows loaded by `make db-init`
src/tasks/                # one task implementation (scope comes from the manifest)
src/gates/                # functional_parity (+ its case corpus), network_isolation, trace_similarity
src/env/                  # environment adapters: start, drive, inspect a sample
src/harness/              # the one CLI harness; the command comes from .env
out/runs/<run_id>/        # task.json, diff.patch, cases/*.json, gates/*.json (gitignored)
```

Samples carry their own environment: **`compose.yaml` lives in the sample
repo**, not here, and is part of the pinned commit. The harness exports
`APP_HTTP_PORT` / `APP_DB_PORT` per run (`BENCH_HTTP_PORT` / `BENCH_DB_PORT`
is still exported for samples pinned before the rename) and gives each run
its own compose project (`bench-<run_id>`), so concurrent runs never
collide on files or ports.

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
# re-pin: set sample.commit_sha in seeds/samples.json, then
make db-init                             # the seed wins over the old row
make case-capture MANIFEST_ID=<n> CASE=<case> SAMPLE_SANDBOX=/abs/tmp/capture-<n>
```

There is no `make pin`: the pin is data in `seeds/samples.json` (tracked
and reviewable), and `make db-init` is the only writer. Pinning through the
DB would have been silently reverted by the next `db-init`.

`expect.json` is always **generated** by `case-capture` from the pristine
tree — never hand-written.

## Status

v1.0 — the rewrite is complete: registry, both verbs, three gates, 17 cases
and 13 manifests migrated. Not yet done: the trace adapter + oracle
(`trace_similarity` stays `pending`), and `compose.yaml` for `openclinica`.
See `ROADMAP.md` for decisions of record, `AGENTS.md` for the agent
contract, and `specs/` for the normative definitions.
