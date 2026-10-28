# SPEC — `behavior.md` (verbs, lifecycle, gates)

Two verbs, plus three support verbs. Nothing else is public.

```bash
make db-init                                    # build bench.db from schema + seeds
make task  MANIFEST_ID=<n> SAMPLE_LOCATION=<path> [HARNESS=<label>]      # → run_id
make gate  GATE_ID=<id> RUN_ID=<run_id> [GATE_VERSION=<n>]             # → value
make case-capture SAMPLE=<s> CASE=<c> SAMPLE_LOCATION=<path>           # freeze golden
make pin   SAMPLE=<s> SAMPLE_LOCATION=<path>                           # re-pin commit
```

The harness is a command, not a name: `BENCH_HARNESS_CMD` in `.env`, or
`HARNESS_CMD` / `--harness-cmd` for one run, with the prompt on stdin.
`HARNESS` is only the label recorded with the run. Everything is also
reachable directly via `python3 main.py …`, which is the stable
interface; the Makefile is a convenience wrapper with no logic.

## 1. `task` — start a run

Inputs: a **manifest** (sample + task type + version + prompt + adapter
bindings + case scope) and **where the sample lives on this filesystem**.

`SAMPLE_LOCATION` is only a path. It is *not* a provenance claim: the
pinned commit comes from `SAMPLE.commit_sha` via the manifest.

Steps:

1. Load manifest → sample → pin. Resolve bindings.
2. **Precondition — pinned checkout.** In `SAMPLE_LOCATION`:
   - if `HEAD != SAMPLE.commit_sha`, `git checkout --detach <sha>`;
   - if the worktree is dirty after that, **abort** (`PreconditionError`).
     No stash, no reset, no force.
   - `SAMPLE.entrypoint` must exist in the checkout, else abort.
3. Allocate `run_id = uuid4().hex`, create `out/runs/<run_id>/`.
4. Insert `TASK_RUN` (`started_at`, `harness`, `environment`).
5. Resolve the harness (`--harness`, default `command`) and run it with
   the **filled prompt**: the manifest prompt verbatim, in the sample
   checkout. The agent is told nothing else — see §5.
6. Capture `diff.patch` = `git diff` of the worktree against the pin
   (empty if the agent changed nothing).
7. Write `out/runs/<run_id>/task.json` and `harness.json`
   (`{harness, exit_code, duration_s, cost_usd, tokens, log,
   diff_bytes, diff_empty}` plus the manifest snapshot and preconditions).
8. Print the `run_id` on stdout and nothing else. Exit 0.

The runner does **not** start the stack. The run is finished when the
harness returns; gates are independent and never decide that. A non-zero
harness exit is recorded, not raised.

## 2. `gate` — evaluate a run

Inputs: a gate id (plus optional version) and a `run_id`.

Steps:

1. Load run → manifest → sample → bindings → case scope.
2. Start the stack from `SAMPLE.entrypoint` inside `SAMPLE_LOCATION`,
   using the sample's own `compose.yaml` and `.env`. The harness injects
   an override: project name `bench-<run_id>`, allocated host ports,
   fixed healthcheck wait. The app is up when healthchecks pass.
   Gates that only read declarations (`network_isolation`) skip this step
   entirely and render the compose files instead.
3. Evaluate, write `out/runs/<run_id>/gates/<gate_id>.json`.
4. Tear the stack down (`down -v`) unless `KEEP_STACK=1`.
5. Print the result JSON on stdout. Exit 0 on `pass`, 1 on `fail`,
   2 on `error`, 3 on `pending`.

### Result document

```json
{
  "gate_id": "functional_parity",
  "gate_version": 1,
  "run_id": "3f2c…",
  "value": 1.0,
  "verdict": "pass",
  "threshold": 0.999,
  "direction": "maximize",
  "duration_s": 812.4,
  "measured_at": "2026-10-27T10:11:12Z",
  "details": [{"case": "vote-flow__upvote-increments-count", "verdict": "pass"}]
}
```

`verdict` ∈ `pass | fail | error | pending`. `value` is normalised to
`[0,1]`, or `null` when the gate cannot measure. A gate **never**
averages: `pass` requires every sub-check to pass.

There is no ordering between gates and no composite score. Three gates
exist today; more will be added (RL environments consume them
individually).

## 3. The three gates

### `functional_parity` — direction `maximize`, threshold `1.0`

For every case in `scope_json.cases`:

1. reset the stack (`down -v && up --wait`), so ids are deterministic;
2. `DatabasePort.dump` of the case's tables → **before**;
3. run `flow.py` through `BrowserPort`, getting its artifacts dict;
4. `DatabasePort.dump` → **after**; compute
   `inserted/updated/deleted` per table with `key_columns` /
   `ignore_columns` applied;
5. compare, order-insensitively, against `expect.json.db`;
6. compare each artifact listed in `case.json.e2e.artifacts` against
   `expect.json.artifacts` (exact string match; DOM is normalised by
   `flow.py` itself);
7. **log the case** to `out/runs/<run_id>/cases/<case>.json` (verdict,
   detail, artifacts, actual DB delta). This is the only way another gate
   may observe a case's outcome — the corpus stays private to this gate.

`value = passed_cases / total_cases`. A case that throws is `error` for
that case and forces the gate to `fail` (not `error`) if other cases
were measurable; if *no* case could run, the gate is `error`.

### `network_isolation` — direction `maximize`, threshold `1.0`

Asserts the stack's **declared** topology conforms to the sample's pinned
shape (`templates/compose.template.yaml`): the work was done and no
hidden dependency was introduced.

**Static.** No container is started. Both files are rendered with
`compose config` (about 0.1 s) — the contract from
`git show <commit_sha>:compose.yaml`, the submission from the worktree —
and the two documents are compared. Reading the worktree for the contract
would let an agent widen the allowance it is measured against.

Assertions:

- no service uses `network_mode:` (`host` or `service:`);
- every service attaches only to networks the pin declares;
- every service publishes only the ports the pin declares for it;
- `db` attaches to `data` only;
- `front` shares no network with `db` — this is the task.

`value = passed_assertions / total_assertions`.

The pinned shape attaches `front` to both networks (the pristine app is
server-rendered and talks to the database directly), so on an untouched
tree this gate **fails** while `functional_parity` **passes**. That
disagreement is the point: parity proves the goldens still reproduce,
isolation proves the work has not been done yet. One repository, one
application: `front` and `back` are built from the same context, so the
data side is isolatable and the frontend can be refactored later.

Known limit (v1): outbound egress is *not* blocked or measured; the gate
reads shape, not traffic. Blocking egress belongs to the runner's
network policy, not to a gate.

### `trace_similarity` — **pending**

Intent: capture OpenTelemetry traces for a run and compare them with an
oracle (possibly an LLM) to detect calls that would violate the new
decomposition — e.g. a controller still reaching into a view layer, or a
new cross-module call that did not exist before.

v1 ships the contract only: if `out/runs/<run_id>/traces.json` is
missing, or `config.TRACE_ORACLE` is `none`, the gate writes
`{"value": null, "verdict": "pending"}`. It must never fabricate a score.
`traces.json` shape (produced by a trace adapter, not by this gate):

```json
{"resource": {"service.name": "mamute"},
 "spans": [{"name": "POST /voto/positivo", "trace_id": "…",
            "parent_id": null, "attributes": {"http.method": "POST"}}]}
```

## 4. Parallel runs

Two runs may execute concurrently on the same machine, even on the same
sample checkout, without sharing mutable state:

| resource | why it cannot collide |
|---|---|
| files | every path is `out/runs/<uuid4>/…`; no timestamps, no reuse |
| writes | `os.replace()` of a temp file in the same directory (atomic) |
| docker | project name `bench-<run_id>`; no shared containers/volumes |
| ports | each run reserves free host ports (`src/run/net.py`) and injects them as a compose override |
| sqlite | WAL mode, one short transaction per write, no long-lived writer |

Two runs on the **same checkout** are still serialised by the sample
itself (both would mutate the same worktree). Run them on separate
clones; the bench never locks the sample.

## 5. Isolation — the agent must not know

An evaluated agent must not be able to tell it is being evaluated:

| never given to the agent | why |
|---|---|
| this repo (`bench.db`, `seeds/`, `specs/`, `src/`) | it contains the prompts, gates and corpus |
| `scope_json` (routes, case names) | it is the answer key's index |
| `expect.json`, `images/` | the answer key itself |
| env vars branded `BENCH_*` | the agent may print its environment |

`HarnessTask` holds only `prompt` and `cwd`, so this is structural, not a
convention. The prompt is the manifest prompt verbatim, phrased as a work
request in the product — no "benchmark", "golden", "parity", "case" or
"evaluation" vocabulary. Enforcing OS-level isolation of the spawned
environment is the **supervisor's** job: it owns this repo and hands the
agent nothing but a checkout and a prompt.

## 6. Determinism

- locale `en-US`, timezone `UTC`, viewport `1280x800` — from
  `config.py`, copied into every browser context.
- credentials come from the sample's `.env` (never from a case file, and
  never hardcoded in `flow.py`).
- ids come from a freshly reset stack (`requires_db_reset`).
- nothing depends on wall-clock time or host locale.
