# SPEC — `modules.md` (repo layout and module boundaries)

## Tree

```
jsp-decouple-bench/
├── Makefile                  # thin wrapper, no logic
├── README.md                 # what this is + the two commands
├── AGENTS.md                 # contract for an evaluated agent
├── ROADMAP.md                # decisions of record
├── main.py                   # CLI entrypoint (argparse only)
├── config.py                 # EVERY tunable, path and env read
├── schema.sql                # DDL for bench.db
├── bench.db                  # git-tracked registry
├── .env.example              # synthetic, deterministic credentials
├── specs/                    # er.md, modules.md, behavior.md
├── seeds/                    # row data loaded by `make db-init`
│   ├── technologies.json
│   ├── samples.json
│   ├── task_types.json
│   ├── gates.json
│   └── manifests.json
├── cases/<sample>/<case>/    # behaviour cases (see below)
│   ├── case.json
│   ├── expect.json
│   ├── flow.py
│   └── images/               # golden-run screenshots (review only)
├── out/                      # gitignored; ALL output
│   └── runs/<run_id>/
└── src/
    ├── errors.py
    ├── store/                # sqlite: connection + repositories
    ├── run/                  # run_id, paths, net, sample checkout, compose stack
    ├── tasks/                # TASK TYPE implementations
    ├── gates/                # GATE implementations
    └── harness/              # capability ports + technology adapters
```

## Dependency rule

```
main.py → tasks | gates → harness.ports → harness.adapters → (subprocess)
             ↓
           src.run, src.store, config
```

- **Nothing imports upward.** An adapter never imports a gate; a gate
  never imports another gate.
- `src/tasks` and `src/gates` talk to the outside world **only** through
  the protocols in `src/harness/ports.py`. A gate that needs a browser
  asks for `BrowserPort`; it does not import Playwright.
- `config.py` is a leaf: every other module may import it, it imports
  nothing local.

## `src/tasks` — task types

One package per row of `TASK_TYPE`, each exporting `RUNNER`:

| package | meaning |
|---|---|
| `decouple_slice/` | one feature boundary: RESTify it, keep parity |
| `oneshot_decoupling/` | the whole app in one shot |

Each implements `src/tasks/ports.py::TaskInputPort`:

```python
class TaskInputPort(Protocol):
    def prepare(self, ctx: RunContext) -> TaskResult: ...
```

`prepare` asserts the sample checkout, snapshots the tree, records the
manifest/prompt into `out/runs/<run_id>/task.json` and returns the run
metadata. It does **not** apply the agent's changes — the harness that
owns `TASK_RUN.harness` does that, and the gates judge the result.

## `src/gates` — gates

One package per `GATE.gate_id`, each exporting `GATE`:

| package | capability used | status |
|---|---|---|
| `functional_parity/` | `StackPort`, `BrowserPort`, `DatabasePort` | implemented |
| `network_isolation/` | `StackPort` | implemented |
| `trace_similarity/` | trace file + oracle | **pending** (emits `verdict: "pending"`) |

Each implements `src/gates/ports.py::GateInputPort`:

```python
class GateInputPort(Protocol):
    def evaluate(self, ctx: RunContext) -> GateResult: ...
```

A gate receives the run context (sample, manifest, bindings, paths) and
returns a `GateResult`; `src/run/artifacts.py` serialises it. Gates never
write to the DB.

## `src/harness` — ports and adapters

`ports.py` declares capabilities (**what** is needed):

| port | methods |
|---|---|
| `StackPort` | `up()`, `down()`, `ps()`, `base_url()`, `inspect()` |
| `BrowserPort` | `run_case(case, base_url, env)`, `capture_case(...)` |
| `DatabasePort` | `list_tables()`, `dump(tables)` |

`adapters/` holds implementations (**who** provides it), one directory
per **technology**, never per sample:

```
adapters/
├── compose/stack.py        # any sample with a compose.yaml      → StackPort
├── playwright/browser.py   # chromium, pinned locale/tz/viewport  → BrowserPort
├── mysql/db.py             # mysql client inside the db service   → DatabasePort
├── postgres/db.py          # psql inside the db service           → DatabasePort
└── h2/db.py                # file/stdio H2 (single-container apps) → DatabasePort
```

Adapters are **reused across samples**; the per-run map from capability
to concrete adapter is `TASK_MANIFEST.bindings_json` (see `er.md`). That
is the whole point: `mysql@1` serves `mamute` and `online-study-system`
without either sample being mentioned in `src/`.

`src/harness/registry.py` resolves `"mysql@1"` → the adapter class,
raises `UnknownAdapter` otherwise, and checks the adapter declares the
capability the binding claims.

## `cases/`

Self-contained behaviour cases, keyed by sample slug (a case name is
unique inside a sample, and samples can never collide):

```
cases/mamute/vote-flow__upvote-increments-count/
├── case.json      # e2e contract + db contract, one file
├── expect.json    # frozen golden: db delta + flow artifacts
├── flow.py        # Playwright flow — the single source of truth
└── images/        # screenshots from the golden capture (review only)
```

`case.json`:

```json
{
  "sample": "mamute",
  "case": "vote-flow__upvote-increments-count",
  "e2e": {"routes": [...], "locale": "en-US", "timezone_id": "UTC",
          "viewport": {"width": 1280, "height": 800},
          "auth": "mixed", "credentials": "env:MAMUTE_ADMIN_USER,MAMUTE_ADMIN_PASSWORD",
          "requires_db_reset": true, "artifacts": ["vote_count_before", "..."]},
  "db":  {"tables": [{"name": "Vote", "key_columns": ["id"],
                      "ignore_columns": ["createdAt"]}]}
}
```

`expect.json` is **generated** by `make case-capture`, never hand-written.

## `out/`

```
out/runs/<run_id>/
├── task.json                 # manifest snapshot + preconditions + diff
├── gates/functional_parity.json
├── gates/network_isolation.json
├── gates/trace_similarity.json
├── diff.patch
├── images/                   # per-run screenshots (review only)
└── traces.json               # OTel capture, when an adapter provides it
out/traces.db                 # cross-run trace index (run_id column)
```

`out/` is gitignored in full; nothing under it is a source of truth.
