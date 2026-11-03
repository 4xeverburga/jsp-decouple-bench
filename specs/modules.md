# SPEC — `modules.md` (repo layout and module boundaries)

## Tree

```
jsp-decouple-bench/
├── main.py                  # the @task types AND the command line
├── settings.py              # EVERY parameter, read from .env; no defaults
├── pyproject.toml, uv.lock  # dependencies live here and nowhere else
├── AGENTS.md                # the supervisor's contract
├── ROADMAP.md               # direction
├── specs/                   # modules.md, behavior.md
├── seeds/                   # samples.json, task_types.json, manifests.json
│   └── prompts/             # task_types/<name>.md, manifests/<name>.md
├── out/                     # gitignored; ALL output
│   ├── solves/<run_id>/     # record.json, diff.patch, tree/
│   ├── workspaces/<run_id>/ # the tree an agent is given
│   ├── evals/               # Inspect logs
│   ├── traces/<slug>/       # a case's spans, taken before `down -v`
│   └── evidence/<slug>/     # a failing case's screenshot
└── src/
    ├── agents/              # native ReAct agent and CLI agent registry
    ├── bench/               # the harness
    └── samples/<slug>/      # one folder per sample; there will be many
        ├── cases/<case>/    # the answer key: case.json, flow.py, expect.json
        └── env/             # compose.yaml, Containerfile, .env, solve.yaml,
                             # otel-collector.yaml, toolbox/
```

## `src/bench`

| module | owns |
|---|---|
| `cli.py` | `task`, `score`, `manifests`; the run id the two phases share |
| `seeds.py` | sources, manifests, task types, and `work_order()` |
| `samples.py` | `(source, case)` pairs as Inspect `Sample`s |
| `compose.py` | where a sample's scoring stack and solve workspace are |
| `stack.py` | starts and removes a case's compose project from the host |
| `solves.py` | a run id, its tree and its diff |
| `replay.py` | the score phase's solver: plays a case once, keeps what it saw |
| `capture.py` | freezes a case's golden and trace base from the pin |
| `scorers/` | one package per gate, `metrics.all_must_pass`, and `observation` — where the replay leaves what it saw |

`settings.py` sits at the repository root, not in `src/bench`, because every
module imports it and it must not depend on the package it configures. It
reads `.env` once and exposes the parameters as module values; a missing key
is an error, never a fallback.

Inspect owns the agent's sandbox, the run lifecycle and the logs. The bench
keeps what no framework supplies: the work order, the case corpus, the delta
algorithm and the shape rules.

## Dependency rule

```
main.py → cli → solves, stack, compose, seeds, settings
        → agents → inspect_ai / inspect_swe
        → replay → stack, scorers.functional_parity (db, cases, delta)
        → scorers → settings   (a scorer never imports another scorer;
                                both read the replay via scorers.observation)
```

- `settings` and `seeds` are leaves. `settings` is importable from anywhere
  because the repository root is on `sys.path` at every entry point.
- Only `stack.py` talks to `docker compose` for scoring; scorers ask it for
  a running stack and never shell out themselves.
- `src/agents/react.py` builds the Inspect-native ReAct agent using
  sandbox-backed shell and text-editor tools. `src/agents/registry.py` is
  the table of every agent a solve can run — the `inspect_swe` CLI rows and
  their model bridge, plus the native row, which has no bridge (`param=None`).
- Agent implementations are selected through `src/agents/`; the harness
  does not depend on a particular CLI agent.
- Nothing under `src/samples/` is Python the bench imports. A flow is loaded
  **by path**, so adding a case never means touching `src/bench`.

## `src/bench/scorers/functional_parity/`

The gate and the machinery that grades a case; nothing else reads the case
layout.

| file | role |
|---|---|
| `parity.py` | the scorer: browser artifacts and database rows, compared |
| `cases.py` | play a case's flow (`drive`), read its golden, compare (`play`), read its hand-written contract |
| `delta.py` | before/after table deltas — the algorithm the goldens froze, so capture and replay agree |
| `db.py` | table snapshots through the case's stack (`compose exec`), in the manifest's dialect |
| `tabular.py` | the TSV parser every SQL client shares |
| `artifacts.py` | the normalizer: base URL, clocks, inline styles |

`db.Target` is built from `bindings.db.options` — `dialect` (`mysql` or
`postgres`), `service`, `database`, `user`, `password`. Both clients are
driven into the same unaligned TSV shape, so only the argv and the
identifier quoting differ.

## `src/bench/scorers/trace_similarity/`

| file | role |
|---|---|
| `similarity.py` | the scorer: a deterministic floor, then the judge |
| `spans.py` | the collector's OTLP file, condensed to a request tree, rendered as text |
| `base.py` | the case's trace base, `trace.json`, frozen beside `expect.json` |
| `judge.py` | the score profile's model, the verdict schema, the conjunction |
| `judge.md` | the judge's prompt — the bench's, never the agent's |

## `src/bench/capture.py`

The only writer of a golden. For each case: one stack from the pin,
snapshot the tables `case.json` declares, play the flow once, snapshot
again, and write `expect.json` (`sample`, `case`, `sample_commit`,
`captured_at`, the `db` delta, the `artifacts`), and from the same run's
spans `trace.json` (`trace_similarity.base.freeze`). It is host-side for the
same reason scoring is, and it never compares against the golden it
replaces.

## `src/samples/<slug>/cases/<case>/`

```
case.json      # hand-written contract: e2e notes + the db table specs
               # (capture reads the table specs; replay reads only the golden)
expect.json    # frozen golden (captured by `main.py capture`, never hand-written)
trace.json     # frozen trace base, condensed spans of that same capture
flow.py        # Playwright flow: `run(page, base_url) -> artifacts`
images/        # optional step shots kept from an investigation
```

`case.json` names the routes, the artifacts compared and, per table, the
`key_columns` and `ignore_columns` of the delta. Credentials are read from
the environment, never written in a case or a flow; `cli.capture` and
`cli.score` inject the sample's `env/.env` into the process.

## `src/samples/<slug>/env/`

The stack is the bench's, never the tree's: the agent gets a checkout with no
stack file in it. The pin carries none — `solves.materialise` refuses a tree
that does, because a sample pinned with one is prepared wrong, not scrubbed
(`prepare-repo-for-dataset`).

| file | role |
|---|---|
| `compose.yaml`, `Containerfile` | the scoring stack, built from the tree under test |
| `.env` | synthetic, deterministic credentials and `OTEL_*`; tracked on purpose |
| `otel-collector.yaml` | receives spans, writes `/traces/traces.jsonl` |
| `solve.yaml`, `toolbox/` | the agent's workspace: toolchain, a writable checkout, a database |

### The solve workspace contract

What a new sample's `env/solve.yaml` and `env/toolbox/Containerfile` have
to honour, so that nothing has to be special-cased per sample:

- **Mount the checkout at `settings.SOLVE_ROOT`** (`/workspace`), never at
  the host path: `- ${BENCH_CHECKOUT:?}:${SOLVE_ROOT:?}`, `working_dir:
  ${SOLVE_ROOT:?}`. The host path spells this repository's name, and `pwd`
  is enough to send an agent looking for it; the driver passes `SOLVE_ROOT`
  to `docker compose` and starts the agent there.
- **Put every tool in `/usr/local/bin`.** The agent's shell is given
  `PATH=/usr/local/bin:/usr/bin:/bin` regardless of what the image sets, so
  an `ENV PATH=` line reaches the image's own shell and nothing else.
- **No OpenTelemetry.** Spans belong to the scoring stack; the solve
  workspace starts neither a collector nor a javaagent.
- **Keep the database a sidecar**, reachable by service name, and make sure
  the app can be pointed at it without editing tracked files.
- **Warm `~/.m2` in the toolbox, from the pin.** A solve with an empty cache
  pays the whole Maven download before the agent can compile anything
  (minutes); with it, a full recompile is seconds. The build context is
  therefore the sample tree — the same context the scoring image builds
  from — so `toolbox/Containerfile` can `COPY` the pom(s) and run the build
  the agent will run (`mvn -B -q compile`, or `package` for a WAR sample)
  before the sources are copied in, then again after: the second run is what
  proves the cache complete, and it must be the layer that can fail. Nothing
  copied in is what the agent reads: the checkout is bind-mounted over
  `SOLVE_ROOT` at run time.
  ```yaml
  build:
    context: ${BENCH_CHECKOUT:?set BENCH_CHECKOUT}
    dockerfile: ${BENCH_SAMPLE_ENV:?set by the bench}/toolbox/Containerfile
  ```
  Not `dependency:go-offline`: it asks every repository the poms declare —
  the pins carry snapshot and Restlet repositories — for every artifact of
  every plugin, and on `mamute` it had not finished after thirteen minutes
  where the build itself takes about eight. `main.py task` builds the
  toolbox before the eval starts (`cli._build_toolbox`), because
  `docker compose up` — what the sandbox runs — never rebuilds an image
  that already exists and its startup is on a timer; the download belongs
  before the clock, where it can be watched.


## `out/`

`out/` is gitignored in full; nothing under it is a source of truth.
