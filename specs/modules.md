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
├── seeds/                   # sources.json, task_types.json, manifests.json
├── templates/               # how a sample's compose stack is shaped
├── out/                     # gitignored; ALL output
│   ├── solves/<run_id>/     # record.json, diff.patch, tree/
│   ├── workspaces/<run_id>/ # the tree an agent is given
│   ├── evals/               # Inspect logs
│   └── evidence/<slug>/     # a failing case's screenshot
└── src/
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
| `scorers/` | one package per gate, plus `metrics.all_must_pass` |

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
        → scorers → stack, settings   (a scorer never imports another scorer)
```

- `settings` and `seeds` are leaves. `settings` is importable from anywhere
  because the repository root is on `sys.path` at every entry point.
- Only `stack.py` talks to `docker compose` for scoring; scorers ask it for
  a running stack and never shell out themselves.
- Only `main.py` imports `inspect_swe`: the agent is the one place the
  evaluated party enters the code.
- Nothing under `src/samples/` is Python the bench imports. A flow is loaded
  **by path**, so adding a case never means touching `src/bench`.

## `src/bench/scorers/functional_parity/`

The gate and the machinery that grades a case; nothing else reads the case
layout.

| file | role |
|---|---|
| `parity.py` | the scorer: browser artifacts and database rows, compared |
| `cases.py` | play a case's flow, read its golden, stage a screenshot |
| `delta.py` | before/after table deltas — copied verbatim, because the goldens were produced by it |
| `db.py` | table snapshots through the case's stack (`compose exec`) |
| `tabular.py` | the TSV parser every SQL client shares |
| `artifacts.py` | the normalizer: base URL, clocks, inline styles |

## `src/samples/<slug>/cases/<case>/`

```
case.json      # e2e contract + db contract (hand-written)
expect.json    # frozen golden (captured, never hand-written)
flow.py        # Playwright flow: `run(page, base_url) -> artifacts`
images/        # screenshots from the golden capture (review only)
```

`case.json` names the routes, the artifacts compared and, per table, the
`key_columns` and `ignore_columns` of the delta. Credentials are read from
the environment, never written in a case or a flow.

## `src/samples/<slug>/env/`

The stack is the bench's, never the tree's: the agent gets a checkout with no
container files in it (`solves.CONTAINER_FILES` strips them).

| file | role |
|---|---|
| `compose.yaml`, `Containerfile` | the scoring stack, built from the tree under test |
| `.env` | synthetic, deterministic credentials and `OTEL_*`; tracked on purpose |
| `otel-collector.yaml` | receives spans, writes `/traces/traces.jsonl` |
| `solve.yaml`, `toolbox/` | the agent's workspace: toolchain, a writable checkout, a database |

## `out/`

`out/` is gitignored in full; nothing under it is a source of truth.
