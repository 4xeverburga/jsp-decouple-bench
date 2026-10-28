# ROADMAP — JSP-Decouple-Bench

**Resume here.** Branch `refactor/harness-ports-and-adapters`, last commit
`84608ea`, worktree clean, not pushed. Everything below is either *done*
(verified), *next* (ordered, with commands), or *considered* (with a cost).

Size today: **2 432 lines of harness code** + **1 653 lines of case
scripts** (`flow.py` × 17, data not logic). Breakdown: `main.py` 269,
`src/env` 561, `src/gates` 575, `src/run` 355, `src/store` 252,
`src/harness` 238, `src/tasks` 80.

---

## 1. Where we are

It started as a rewrite and has become the real thing: a registry plus two
verbs, three gates, and an agent-harness boundary that keeps the agent
blind to being measured.

| thing | state |
|---|---|
| `bench.db` (7 tables + `v_run`, `PRAGMA user_version` guard) | 3 samples, 13 manifests, 3 gates, 0 runs |
| `src/gates/functional_parity/cases/` | 17 cases (case.json + expect.json + flow.py + images) |
| gates | `functional_parity` ✔, `network_isolation` ✔, `trace_similarity` **pending** |
| environment adapters (`src/env`) | compose, playwright, mysql, postgres, h2, shell |
| agent harnesses (`src/harness`) | command, claude-code, opencode, pi |
| docs | README, AGENTS (supervisor), specs/{er,modules,behavior}, test-slice skill |

Verified by running it, not by reading it:

- `make db-init` → 3 / 13 / 3, and the drift guard refuses a stale schema.
- `make task` → run id, `task.json`, `harness.json`, `diff.patch`, `TASK_RUN` row.
- dirty sample → `PreconditionError`, no partial run trusted.
- `HARNESS=command` with an env-dumping agent → prompt byte-identical to the
  manifest prompt, **zero `BENCH_*` variables**, `PATH` intact.
- gates on a sample with no compose → `error` / `value: null` / exit 2
  (never a fabricated score); `trace_similarity` → `pending` / exit 3.

**Not yet proven: a green `functional_parity` on an untouched tree (no-op agent).** That is
step 1 below and the only number that means anything so far.

## 2. Tomorrow, in order

### 2.1 The self-check (do this first)

`compose.yaml` + `Dockerfile` + `.env.example` are sitting **uncommitted**
in `../mamute` and `../Online_Study_System`, so the pinned commits do not
contain them and the harness refuses to start.

```bash
cd ../mamute && git add -A && git commit -m "bench: add compose stack" && cd -
cd ../Online_Study_System && git add -A && git commit -m "bench: add compose stack" && cd -

make pin SAMPLE=mamute              SAMPLE_LOCATION=../mamute
make pin SAMPLE=online-study-system SAMPLE_LOCATION=../Online_Study_System

RUN=$(make task SAMPLE=mamute TASK=vote-flow SAMPLE_LOCATION=../mamute HARNESS=command HARNESS_CMD=true | tail -1)
make gate GATE_ID=functional_parity RUN_ID=$RUN   # must be pass, value 1.0
make gate GATE_ID=network_isolation RUN_ID=$RUN   # must be pass
```

If `functional_parity` fails on a no-op run, the **sample or the environment
is wrong**, not the agent — fix that before recording any agent score.

### 2.2 `openclinica`

No compose file (its old env was podman-driven). Either author
`openclinica/compose.yaml` (postgres + liquibase + tomcat) and switch the
manifest's `db` binding from `shell@1` to `postgres@1`, or keep it out of
the sample set for now. Right now it is a sample that cannot be scored.

### 2.3 Trace capture, then `trace_similarity`

The gate is spec'd and stubbed. What is missing is the producer: an adapter
that captures OTel spans into `out/runs/<run_id>/traces.json`. The gate
then compares against an oracle (`BENCH_TRACE_ORACLE_CMD`, contract in the
gate's docstring). Until both exist it must keep saying `pending`.

### 2.4 First real agent run

```bash
make task SAMPLE=mamute TASK=vote-flow SAMPLE_LOCATION=../mamute \
          HARNESS=claude-code        # or opencode / pi / command
make gate GATE_ID=functional_parity RUN_ID=$RUN
```

Check `harness.json` (exit code, cost) and `diff.patch` (the agent actually
worked) before believing the gate. A `diff_empty: true` means the harness
never ran or produced nothing — a gate failure then says nothing about the
agent's ability.

## 3. Ideas to shrink the code

Ordered by (saving ÷ risk). Items 3.1–3.4 are one coherent change set: they
de-duplicate the *wiring*, not the behaviour, and should land as 2 commits.

| # | Idea | Saving | Risk | Verdict |
|---|---|---|---|---|
| 3.1 | **One SQL adapter.** `mysql@1` and `postgres@1` are the same class with a different argv and identifier quote; `h2@1` is already `shell@1` plus a default query. Make them one `sqlclient` adapter configured by the binding (`argv`, `quote`, `list_tables_sql`). | ~95 | low — the TSV parser is already shared | do it |
| 3.2 | **One registry.** `env/`, `gates/` and `harness/registry.py` are the same 20-line `dict + importlib` dance. Extract `src/registry.py::load(table, key)`; each package keeps its table. | ~40 | low | do it |
| 3.3 | **One `GateResult` factory.** All three gates repeat the same 15-line constructor call and only `trace_similarity` uses the threshold comparison. Add `GateResult.build(definition, ctx, verdict, value, details)` and `.compare(value)`. | ~35 | low | do it |
| 3.4 | **Presets are data.** `claude-code`/`opencode`/`pi` are `name` + default command; move them into the harness table and delete `presets.py`. | ~30 | low | do it |
| 3.5 | **Delete the Protocol-only port files** (`env/ports.py`, `gates/ports.py`). Nothing enforces them at runtime; `specs/modules.md` already states both contracts. Keep `harness/ports.py` — it holds the dataclasses and the two-field rule. | ~45 | medium — you lose the only in-code statement of "gates never import harness" | only if you want the LOC |
| 3.6 | **`network_isolation`** does three checks inline per container (132 lines). A `_checks(container) -> list[CaseResult]` helper is ~85. | ~50 | low | optional |
| 3.7 | **Merge `run/{paths,atomic,net}.py`** into one `run/io.py`. | ~20 | low | skip — each file is one idea |
| 3.8 | **`store/db.py::_seed`** is 90 lines of upserts that only pay off when re-seeding over an existing `TASK_RUN` history. Replacing it with drop-and-insert costs ~40 lines but throws history away. | ~40 | high | skip |

Realistic total: **~250 lines (≈10 %)** without touching behaviour. Below
that, further cuts start removing either the contract or the history.

## 4. Ideas that *add* lines but earn them

Ranked by value, since two of these would have caught bugs we already hit.

1. **`make check`** (~60 lines). A temp-DB smoke test that:
   - builds `bench.db` into a temp path and asserts the row counts;
   - resolves **every** adapter, gate and harness in the catalogues;
   - asserts every `scope.cases` entry exists on disk with an `expect.json`;
   - scans every prompt for leak words (`bench`, `golden`, `parity`,
     `evaluat`, `baseline`, `case`) — this is the one that keeps D16 true;
   - asserts `HarnessTask` still has exactly `{prompt, cwd}`.
   Would have caught the manifest-PK collapse and the `BENCH_*` inheritance.
2. **Per-run sample clone** (~40 lines). Today the harness works inside
   `SAMPLE_LOCATION`, so an agent dirties it and a second run refuses. A
   `make task` that clones the pin into `out/runs/<run_id>/sample` makes
   parallel agent comparison possible. This is the biggest functional gap.
3. **`make run`** (~15 lines in the Makefile). `task` + the three gates +
   one summary line, so a run is one command instead of four.
4. **A prompt review pass** — not code. Read the 13 prompts as a developer
   who was handed the ticket: do they name the feature unambiguously
   without naming routes? `select-course-flow` and `study-flow` are the
   vaguest.

## 5. Decisions of record

| # | Decision |
|---|---|
| D1 | `independent_frontend` dropped — weak, gameable eval. |
| D2 | `trace_similarity` stays `pending` until an oracle exists; it never fabricates a score. |
| D3 | Reproducibility = pinned-checkout precondition, not a provenance table. |
| D4 | Environment adapters are selected **by technology**, reused across samples. |
| D5 | The capability → adapter map lives in the manifest (`bindings_json`). |
| D6 | Gate results are files under `out/`, never DB rows. |
| D7 | `make` is a thin `key=value` wrapper; `main.py` is the stable interface. |
| D8 | Only the three specified gates exist. No ordering, no composite score. |
| D9 | `bench.db` tracked; `.env` untracked; `config.py` owns every tunable. |
| D10 | Parallel runs safe by construction (`uuid4`, atomic writes, per-run ports). |
| D11 | `compose.yaml` lives in the sample and is part of the pinned commit. |
| D12 | Edge-case samples stay in scope — if it runs locally, it is a sample. |
| D13 | `TASK_MANIFEST` is identified by `(sample, name, version)`; `task_type` is only the *kind* of work. |
| D14 | The case corpus lives **inside** `functional_parity`; other gates read a case's **logged result** (`out/runs/<id>/cases/<case>.json`), never the corpus. |
| D15 | `src/harness` = agent harnesses; `src/env` = the sample's runtime. |
| D16 | The agent never learns it is being evaluated: `HarnessTask` = `{prompt, cwd}`, prompt verbatim, no `BENCH_*` in the spawned environment. |
| D17 | The supervisor owns isolation and provisioning; the bench only refuses to start from a dirty or unpinned tree. |

## 6. Known gaps

| Gap | Consequence | Where it is fixed |
|---|---|---|
| No green no-op run yet | no score is trustworthy yet | §2.1 |
| `openclinica` has no compose | one sample cannot be scored | §2.2 |
| `trace_similarity` has no producer | gate always `pending` | §2.3 |
| Egress is not measured | `network_isolation` reads shape only | runner-side policy, not a gate |
| No automated checks | regressions are found by running | §4.1 |
| One run = one dirty checkout | serialises agent comparisons | §4.2 |
| No `oneshot_decoupling` manifest | the task type exists but is unused | a seed row (scope must list every case — nothing widens it by discovery) |

## 7. Layout, as built

```
bench.db  schema.sql  seeds/      registry: inputs only
main.py  config.py                the two verbs + every tunable
specs/{er,modules,behavior}.md    the contract
src/run/       run_id, paths, atomic writes, ports, pinned checkout, RunContext
src/store/     sqlite connection + repositories
src/tasks/     one Task: assert pin, hand prompt to harness, record
src/gates/     functional_parity (+ its corpus, capture, delta), network_isolation, trace_similarity
src/env/       StackPort/BrowserPort/DatabasePort + technology adapters
src/harness/   HarnessTask/HarnessResult/HarnessPort + command/presets
out/runs/<run_id>/  task.json, harness.json, harness.log, harness-prompt.md,
                    diff.patch, cases/*.json, gates/*.json
```
