# ROADMAP — JSP-Decouple-Bench

**Resume here.** Branch `refactor/harness-ports-and-adapters`, last commit
`a036e67`, pushed, worktree clean. Everything below is either *done*
(verified), *next* (ordered, with commands), or *considered* (with a cost).

Size today: **3 207 lines of harness code** + **1 739 lines of case
scripts** (`flow.py` × 17, data not logic). Breakdown: `main.py`+`config.py`
479, `src/env` 811, `src/gates` 801 (cases excluded), `src/run` 449,
`src/store` 326, `src/harness` 233, `src/tasks` 108.

---

## 1. Where we are

It started as a rewrite and has become the real thing: a registry plus two
verbs, three gates, and an agent-harness boundary that keeps the agent
blind to being measured.

| thing | state |
|---|---|
| `bench.db` (7 tables + `v_run`, `PRAGMA user_version` = 3) | 3 samples, 14 manifests, 3 gates, 18 runs |
| `src/gates/functional_parity/cases/` | 17 cases (case.json + expect.json + flow.py + images) |
| task types | 2, each with a `base_prompt` prepended to every ask of that type |
| gates | `functional_parity` ✔, `network_isolation` ✔ (grades the pinned compose), `trace_similarity` **pending** |
| environment adapters (`src/env`) | compose, playwright, mysql, postgres, h2, shell |
| agent harnesses (`src/harness`) | command, claude-code, opencode, pi |
| docs | README, AGENTS (supervisor), specs/{er,modules,behavior}, test-slice skill |

Verified by running it, not by reading it:

- `make db-init` → 3 / 14 / 3, and the drift guard refuses a stale schema.
- `make task` → run id, `task.json`, `harness.json`, `diff.patch`, `TASK_RUN` row.
- dirty sample → `PreconditionError`, no partial run trusted.
- `HARNESS=command` with an env-dumping agent → the composed work order
  (base prompt + ask) reaches the agent verbatim, **zero `BENCH_*`
  variables**, `PATH` intact.
- a no-op run on `mamute/answer-flow` → `functional_parity` **pass**,
  `value 1.0`, empty `diff.patch`; repeated five times, including after the
  schema rebuild.
- the first graded agent run (opencode, 36 min, real edits) → **fail**, for
  an AJAX handler that returned early before sending anything: the gate was
  right, the submission was inert.
- gates on a sample with no compose → `error` / `value: null` / exit 2
  (never a fabricated score); `trace_similarity` → `pending` / exit 3.

The no-op run is the number everything else rests on, and it is green. Two
lessons came out of the first real score and are decided in §5: a flow
assertion is a **fail**, not an `error`; and a failed case leaves a
screenshot at `out/runs/<id>/images/<gate>/<case>.png`.

## 2. Next, in order

### 2.1 Parallel-safe runs: one git worktree per run

Today the harness works inside `SAMPLE_LOCATION` itself. Consequences: an
agent dirties the sample repo, the next run refuses to start (AGENTS rule
5), two agents cannot be compared in parallel, and a gate run against a
tree someone else is editing measures the wrong thing. The UUID, the
per-run ports and the atomic writes already make everything *else*
parallel-safe (D10); the sample tree is the last shared mutable object.

Proposal: one `git worktree` per run.

```bash
git -C ../mamute worktree add --detach \
    out/runs/<run_id>/sample <commit_sha>
# agent runs with cwd = that worktree; diff, gates and screenshots read it
git -C ../mamute worktree remove --force out/runs/<run_id>/sample
```

A worktree rather than a clone because it shares the object database (no
copy, instant), `git diff <sha>` behaves identically, `git status` inside it
is that run's alone, and the sample repo stays clean — `make task` no longer
needs a vanilla tree to start from.

Settled by this: `SAMPLE_LOCATION` keeps meaning "the repo holding the pin";
the per-run worktree becomes `ctx.sample_location` for the task and every
gate, and `task.json` records both.

Not settled yet, and each one decides an edge:

- **Untracked-but-needed files.** A fresh worktree only has committed
  files. `mamute` commits `.env`; a sample whose `.env` is untracked would
  start credential-less. Either require the file at the pin or copy it in.
- **Cold build cache.** `target/`, `node_modules/` and the generated assets
  are gitignored, so every run pays a full compile. Accept it, or seed the
  worktree from a warm template.
- **Re-grading an old run.** Today `make gate RUN_ID=…` works because the
  tree is still there. With the worktree removed after the run, an old run
  can only be re-graded by replaying `diff.patch` (§2.8) or by keeping the
  worktree until the run is pruned.
- **Cleanup.** A crashed run leaves a registered worktree; add `make prune`
  and a `KEEP_WORKTREE=1` knob, mirroring `KEEP_STACK`.

Cost: ~50 lines — `src/run` gains worktree create/remove, `RunContext`
carries both paths.

### 2.2 The remaining flows still wait for a navigation

16 of the 17 `flow.py` scripts wrap their graded action in
`expect_navigation(...)` — that is the *pristine* transport, not the
behaviour. The task asks for a JSON call that updates the page, which by
design performs no navigation, so a correct submission is graded as broken.

`answer-flow` is the template: wait for the outcome, turn that timeout into
an assertion carrying diagnostics, and assert count → presence → content.
Apply it to `ask-flow`, both `vote-flow` cases, `watch-flow`, and the
`online-study-system` and `openclinica` flows. The post-state is identical,
so goldens should not move — if one does, that flow was asserting the
transport.

### 2.3 The self-check (re-run after every change)

Every sample commits its stack at the pin (`git show <sha>:compose.yaml`
renders), so nothing needs to be committed to run the self-check. What gets
in the way is the dirty worktree an agent run leaves behind — the harness
refuses to start from a dirty checkout until §2.1 lands. When migrating a
sample's `compose.yaml` to `templates/compose.template.yaml` (two networks,
`front` on both at the pin), re-pin before capturing.

Run it for every manifest of the sample before calling the sample ready:

```bash
# until §2.1 lands the agent run leaves the tree dirty; restore it first
cd ../mamute && git checkout -- . && git clean -fd && cd -

RUN=$(make task SAMPLE=mamute TASK=answer-flow SAMPLE_LOCATION=../mamute HARNESS=command HARNESS_CMD=true | tail -1)
make gate GATE_ID=functional_parity RUN_ID=$RUN   # must be pass, value 1.0
make gate GATE_ID=network_isolation RUN_ID=$RUN   # must FAIL (the pin keeps front on both networks)
```

If `functional_parity` fails on a no-op run, the **sample or the environment
is wrong**, not the agent — fix that before recording any agent score. If
`network_isolation` *passes* on a no-op run, the sample ships pre-decoupled
and has no task left in it: re-pin to the monolithic shape
(`templates/README.md`).

### 2.4 `openclinica`

No compose file (its old env was podman-driven). Either author
`openclinica/compose.yaml` (postgres + liquibase + tomcat) and switch the
manifest's `db` binding from `shell@1` to `postgres@1`, or keep it out of
the sample set for now. Right now it is a sample that cannot be scored.

### 2.5 Trace capture, then `trace_similarity`

The gate is spec'd and stubbed. What is missing is the producer: an adapter
that captures OTel spans into `out/runs/<run_id>/traces.json`. The gate
then compares against an oracle (`BENCH_TRACE_ORACLE_CMD`, contract in the
gate's docstring). Until both exist it must keep saying `pending`.

Sample side (skill `prepare-repo-for-dataset` §3): each sample installs the
OpenTelemetry Java agent in its own `Dockerfile`/`compose.yaml`, pinned,
configured via `OTEL_*` in `.env`, any collector declared in the compose
file. None of the three samples has it yet, so the pristine trace base
cannot be captured for them.

### 2.6 Coverage command and slice retrofit

Skill `test-slice` now requires each slice to fully cover at least one
controller (manifest `scope.covers`). Two gaps:

- there is no coverage command in this rewrite; port
  `scripts/measure-coverage.sh` and `tools/jacoco/` from `main` (JaCoCo
  tcpserver mode, per-case dump, per-sample knobs);
- the 13 existing manifests have no `scope.covers`; their slices were
  authored before the rule and must be measured, then backfilled with
  extra cases or re-scoped.

### 2.7 Run the remaining slices

One real run has been scored (opencode on `mamute/answer-flow`, §1). The
rest are waiting on §2.2 — until a flow stops demanding a navigation, its
verdict says more about the flow than about the agent.

```bash
RUN=$(make task SAMPLE=mamute TASK=vote-flow SAMPLE_LOCATION=../mamute \
             HARNESS=claude-code | tail -1)     # or opencode / pi
make gate GATE_ID=functional_parity RUN_ID=$RUN
```

Check `harness.json` (exit code, cost) and `diff.patch` (the agent actually
worked) before believing the gate. A `diff_empty: true` means the harness
never ran or produced nothing — a gate failure then says nothing about the
agent's ability.

### 2.8 Housekeeping (small, each unblocks something)

- **Flows still carry literal timeouts.** 17 `timeout=` literals across the
  case scripts, and `openclinica/.../flow.py:37` is
  `def _goto(page, url, timeout=60000)` — a default parameter, which rule 9
  forbids outright. `BENCH_CASE_TIMEOUT_MS` exists; a page-level knob and a
  per-sample re-verify are still missing.
- **A recorded patch cannot be replayed.** `diff()` decodes with
  `errors="replace"`, so a non-UTF-8 source (`mamute`'s `showQuestion.jsp`)
  becomes `�` and `git apply` rejects the patch. Write the bytes instead:
  replaying a submission is what makes re-grading or re-screenshotting an
  old run possible at all.
- **The sample's runbook is stale at the pin.** `mamute/AGENTS.md` still
  documents the pre-bench workflow (podman MySQL, `mvn exec:java`, branch
  `main`, a hardcoded `/home/ever/...` path) and never mentions
  `compose.yaml`; an agent that follows it is sent to the wrong stack. Fix
  it in the sample repo, then re-pin.
- **`answer-flow`'s ask is still v1.** The base prompt now demands
  verification and an unchanged markup, but the ask does not name the
  observable outcome (the answer appears and the count goes with it; an
  invalid answer still shows its error). Add a v2 and keep v1 comparable.
- **`src/env/adapters/compose/stack.py` is the only file failing
  `ruff format --check`.**
- **Registry rows can outlive their artifacts.** `bench.db` lists 18 runs
  while `out/runs/` holds one (the newest); gating a pruned run fails with
  "has no task.json", which reads like corruption. Prune the rows together
  with the directories, or say so plainly and offer a re-grade from
  `diff.patch` (which needs the point above).

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
2. ~~Per-run sample clone~~ → promoted to §2.1, as a **worktree** rather
   than a clone: same isolation, no copy of the object database, and
   `git diff <sha>` keeps working inside it.
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
| D10 | Parallel runs safe by construction (`uuid4`, atomic writes, per-run ports). *(The sample tree was the exception — §2.1, D20.)* |
| D11 | `compose.yaml` lives in the sample and is part of the pinned commit. |
| D12 | Edge-case samples stay in scope — if it runs locally, it is a sample. |
| D13 | `TASK_MANIFEST` is identified by `(sample, name, version)`; `task_type` is only the *kind* of work. |
| D14 | The case corpus lives **inside** `functional_parity`; other gates read a case's **logged result** (`out/runs/<id>/cases/<case>.json`), never the corpus. |
| D15 | `src/harness` = agent harnesses; `src/env` = the sample's runtime. |
| D16 | The agent never learns it is being evaluated: `HarnessTask` = `{prompt, cwd}`, prompt verbatim, no `BENCH_*` in the spawned environment. |
| D17 | The supervisor owns isolation and provisioning; the bench only refuses to start from a dirty or unpinned tree. *(Superseded by D20 for the sample tree.)* |
| D18 | A prompt is two data layers: `TASK_TYPE.base_prompt` says what this kind of work means and what it must not break; `TASK_MANIFEST.prompt` says which sliver. Both are recorded per run. |
| D19 | A decoupling must be invisible: the rendered markup is unchanged (same elements, classes and text), so a user or a browser automation sees the same page. A redesign is a failure, not a bonus. |
| D20 | *Proposed, not implemented.* One run = one git worktree of the pin; the sample repo is where the pin lives, never the agent's scratch space. |

## 6. Known gaps

| Gap | Consequence | Where it is fixed |
|---|---|---|
| 16 of 17 flows wait for a navigation | a correct in-place implementation is graded as broken | §2.2 |
| One run = one dirty checkout | serialises agent comparisons, blocks re-runs | §2.1 |
| `openclinica` has no compose | one sample cannot be scored | §2.4 |
| `trace_similarity` has no producer | gate always `pending` | §2.5 |
| Egress is not measured | `network_isolation` reads shape only | runner-side policy, not a gate |
| No automated checks | regressions are found by running | §4.1 |
| Patches are not replayable | an old submission cannot be re-graded | §2.8 |
| Registry rows outlive run dirs | gating a pruned run looks like corruption | §2.8 |

## 7. Layout, as built

```
bench.db  schema.sql  seeds/      registry: inputs only
main.py  config.py                the two verbs + every tunable
specs/{er,modules,behavior}.md    the contract
templates/compose.template.yaml   the stack shape every sample commits
src/run/       run_id, paths, atomic writes, ports, pinned checkout, RunContext
src/store/     sqlite connection + repositories
src/tasks/     one Task: assert pin, hand prompt to harness, record
src/gates/     functional_parity (+ its corpus, capture, delta), network_isolation, trace_similarity
src/env/       StackPort/BrowserPort/DatabasePort + technology adapters
src/harness/   HarnessTask/HarnessResult/HarnessPort + command/presets
out/runs/<run_id>/  task.json, harness.json, harness.log, harness-prompt.md,
                    diff.patch, cases/*.json, gates/*.json
```
