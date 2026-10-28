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
├── out/                      # gitignored; ALL output
│   └── runs/<run_id>/
└── src/
    ├── errors.py
    ├── store/                # sqlite: connection + repositories
    ├── run/                  # run_id, paths, net, sample checkout, compose stack
    ├── tasks/                # the task implementation (scope is data)
    ├── gates/                # gate implementations (+ functional_parity/cases/)
    ├── env/                  # environment adapters: start, drive, inspect a sample
    └── harness/              # agent harnesses: hand the prompt to an agent
```

## Dependency rule

```
main.py → tasks ─→ env.ports → env.adapters → (subprocess)
        → gates ─→ env.ports → env.adapters → (subprocess)
        → tasks ─→ harness.ports → harness.adapters → (the agent)
             ↓
           src.run, src.store, config
```

- **Nothing imports upward.** An adapter never imports a gate; a gate
  never imports another gate; **a gate never imports `src.harness`** — a
  gate judges a tree, it does not run an agent.
- `src/tasks` and `src/gates` talk to a sample's runtime **only** through
  the protocols in `src/env/ports.py`. A gate that needs a browser asks
  for `BrowserPort`; it does not import Playwright.
- `src/tasks` is the only module that talks to `src/harness`.
- `config.py` is a leaf: every other module may import it, it imports
  nothing local.

## `src/tasks` — the task

One implementation. `decouple_slice` and `oneshot_decoupling` differ only
in the manifest's case scope, which is data, so the registry maps both
names to `Task`:

```python
class Task:
    def prepare(
        self, ctx: RunContext, harness: HarnessPort
    ) -> HarnessResult: ...
```

`prepare` asserts the sample checkout, hands the prompt to the **harness**,
reads the resulting diff back from git, and records the run. It does not
start the stack, and it never edits the sample itself.

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

## `src/env` — environment adapters

`env/ports.py` declares what the bench needs from a sample's **runtime**:

| port | methods |
|---|---|
| `StackPort` | `up()`, `down()`, `reset()`, `ps()`, `inspect()`, `declared()`, `exec_()` |
| `BrowserPort` | `run_case(flow_path, base_url, e2e)`, `capture_case(...)` |
| `DatabasePort` | `list_tables()`, `dump()`, `dump_many()` |

`env/adapters/` holds implementations, one directory per **technology**,
never per sample:

```
env/adapters/
├── compose/stack.py        # any sample with a compose.yaml      → StackPort
├── playwright/browser.py   # chromium, pinned locale/tz/viewport  → BrowserPort
├── mysql/db.py             # mysql client inside the db service   → DatabasePort
├── postgres/db.py          # psql inside the db service           → DatabasePort
├── h2/db.py                # H2 via an explicit command           → DatabasePort
├── shell/db.py             # any SQL-over-stdin command           → DatabasePort
└── tabular.py              # shared TSV parsing
```

Adapters are **reused across samples**; the per-run map from capability
to concrete adapter is `TASK_MANIFEST.bindings_json` (see `er.md`). That
is the whole point: `mysql@1` serves `mamute` and `online-study-system`
without either sample being mentioned in `src/`.

`src/env/registry.py` resolves `"mysql@1"` → the adapter class, raises
`UnknownAdapterError` otherwise, and checks the adapter declares the capability
the binding claims.

## `src/harness` — agent harnesses

The **other** meaning of "harness": the thing that runs the **agent**. It
receives the prompt and does the work.

```python
@dataclass(frozen=True)
class HarnessTask:
    prompt: str  # TASK_MANIFEST.prompt — the whole of it
    cwd: Path  # the sample checkout, already pinned

    def render(self) -> str: ...  # exactly what the agent reads


class HarnessPort(Protocol):
    name: str

    def run(self, task: HarnessTask, log_dir: Path) -> HarnessResult: ...
```

| adapter | meaning |
|---|---|
| `command` | any agent CLI: the prompt arrives on stdin |
| `claude-code`, `opencode`, `pi` | presets over `command` |

Rules:

1. **The agent must not know it is being evaluated.** `render()` returns
   the manifest prompt verbatim — no routes, no case names, no goldens,
   no "benchmark" vocabulary. `HarnessTask` holds only `prompt` and `cwd`,
   so verification metadata (`scope_json`) cannot leak, structurally.
2. **The agent's environment is not branded.** `command` adds nothing to
   the environment it spawns. The prompt copy it keeps lives in the run
   directory for the supervisor, and no such path is handed to the agent.
3. **The supervisor is the only party that knows about grading.** It owns
   this repo and spawns environments for agents; an agent may never have
   access to `bench.db`, `seeds/` or the case corpus.
4. The harness is chosen **per run** (`--harness`), not per sample:
   comparing agents is the point. Its name is recorded in `TASK_RUN.harness`.
5. The harness's own claims are never trusted: the diff is read back from
   git and written to `out/runs/<run_id>/diff.patch`.
6. `HarnessResult` carries `exit_code`, `duration_s`, `cost_usd`, `tokens`,
   `log_path`; cost flows into `TASK_RUN.estimated_cost_usd`.

## `src/gates/functional_parity/cases/`

The corpus belongs to the gate that consumes it: **a case is a
functional-parity test**, so it lives inside that package.

```
src/gates/functional_parity/cases/<sample>/<case>/
├── case.json      # e2e contract + db contract (hand-written)
├── expect.json    # frozen golden (generated by `make case-capture`)
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

Nothing outside `functional_parity` knows these paths (`corpus.py` owns
them); the `browser` adapter receives a **flow path**, never a case name.
Other gates read a case's logged result — `out/runs/<run_id>/cases/
<case>.json` — never the corpus. That is the cross-gate interface from
`er.md`.

## `out/`

```
out/runs/<run_id>/
├── task.json                 # manifest snapshot + preconditions + diff
├── cases/<case>.json         # per-case result — the cross-gate interface
├── gates/functional_parity.json
├── gates/network_isolation.json
├── gates/trace_similarity.json
├── diff.patch
├── images/                   # per-run screenshots (review only)
└── traces.json               # OTel capture, when an adapter provides it
```

`out/` is gitignored in full; nothing under it is a source of truth.
