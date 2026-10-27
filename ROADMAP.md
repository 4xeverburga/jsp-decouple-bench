# ROADMAP — rewrite of JSP-Decouple-Bench

Status: **v1.0 shipped** (branch `refactor/harness-ports-and-adapters`).
This was a rewrite, not a refactor. Kept from the old project: the sample
data and the behaviour cases. Everything else was rebuilt.

---

## 1. Decisions of record

| # | Decision | Status |
|---|---|---|
| D1 | `independent_frontend` is dropped — weak, gameable eval. | done |
| D2 | `trace_similarity` exists but is **pending**; no fabricated scores. | done (gate stub) |
| D3 | Reproducibility = pinned checkout precondition, not a provenance table. | done |
| D4 | Adapters are selected **by technology**, reused across samples. | done |
| D5 | The capability → adapter map lives in the manifest (`bindings_json`). | done |
| D6 | Gate results are files under `out/`, not DB rows. | done |
| D7 | `make` is a thin `key=value` wrapper; `main.py` is the interface. | done |
| D8 | `make setup` / `make eval` deleted with every doc reference. | done |
| D9 | `bench.db` is git-tracked; `.env` is not; `config.py` owns tunables. | done |
| D10 | Parallel runs safe by construction (`uuid4`, atomic writes, per-run ports). | done |
| D11 | `compose.yaml` lives in the sample, part of the pinned commit. | done |
| D12 | Edge-case samples stay in scope (Solr, LDAP, …) — local run is the bar. | accepted |
| D13 | Only the three specified gates exist. No ordering, no composite score. | done |
| D14 | The case corpus lives **inside** `functional_parity` (a case is that gate's test); other gates read a case's **logged result**, never the corpus. | done |

## 2. What was built

```
bench.db + schema.sql      registry: technology, sample, sample_technology,
                           task_type, task_manifest, task_run, gate
main.py                    db | task | gate | case | pin
config.py                  every path, port, timeout, env read
seeds/                     9 technologies, 3 samples, 2 task types,
                           13 manifests, 3 gates
src/gates/functional_parity/
  cases/<sample>/<case>/    17 cases: case.json + expect.json + flow.py + images/
  corpus.py                 the only module that knows those paths
  capture.py                freezes expect.json from a pristine checkout
src/run/                   run_id, paths, atomic writes, port allocation,
                           pinned-checkout precondition, adapters context
src/tasks/                 one implementation; scope comes from the manifest
src/gates/                 functional_parity, network_isolation, trace_similarity
src/harness/               ports + adapters: compose@1, playwright@1,
                           mysql@1, postgres@1, h2@1, shell@1
specs/                     er.md, modules.md, behavior.md
```

Verified end to end:

- `make db-init` → 3 samples / 13 manifests / 3 gates.
- `make task MANIFEST_ID=13 SAMPLE_LOCATION=../openclinica` → run id,
  `out/runs/<id>/task.json` + `diff.patch`, row in `TASK_RUN`.
- dirty sample → refused with `PreconditionError` (proven on `../mamute`
  after the environment files were added).
- `make gate GATE_ID=trace_similarity …` → `verdict: pending`, `value: null`, exit 3.
- `make gate GATE_ID=functional_parity …` on a sample with no compose →
  `verdict: error`, `value: null`, exit 2 (no fake score).

## 3. Deviations from the first draft

1. **`TASK_MANIFEST` gained `name`.** The original PK
   `(sample, task_type, version)` cannot distinguish `vote-flow` from
   `ask-flow` — both are `decouple_slice`. The first seed collapsed 13
   manifests into 3. Identity is now `UNIQUE(sample, name, version)`;
   `task_type` is the *kind* of work, `name` is *which* work.
2. **`PRAGMA user_version` + drift guard.** `make db-init` now refuses to
   reuse a `bench.db` built from a different schema version instead of
   silently seeding into a stale shape (`make db-init-force` rebuilds).
3. **`pristine` is the only harness that ships.** `TASK_RUN.harness` is
   free text; the runner records who produced the diff but does not manage
   agents.
4. **Keep `out/runs/<run_id>/images/`** (per-run screenshots) alongside the
   golden `…/functional_parity/cases/<case>/images/`; only the latter is
   tracked.
5. **Cases moved into the gate, and their results are logged.** Moving the
   corpus in removed `RunContext`'s case accessors and `config.CASES_DIR`;
   the `browser` adapter now takes a flow **path** instead of a case name,
   so harness code never learns the corpus layout. Per-case outcomes are
   written to `out/runs/<run_id>/cases/<case>.json` — that file, not the
   corpus, is how another gate observes a case.
6. **One task implementation.** `decouple_slice` and `oneshot_decoupling`
   differed only in scope widening, which is manifest data; the registry
   maps both names to `Task`. Net effect of 5–6: −97 lines of Python.

## 4. Known gaps (deliberate)

| Gap | Why | Unblocks |
|---|---|---|
| No trace adapter, no oracle | `trace_similarity` is spec'd but not measurable yet | D2; blocks nothing else |
| `openclinica` has no `compose.yaml` | its old env was podman-driven, not compose | `network_isolation` / `functional_parity` on that sample |
| Sample environments are **uncommitted** in the sample repos | provenance: the pinned commit must contain `compose.yaml` | run `git add -A && git commit` in each sample, then `make pin` |
| `outbound` egress not measured | `network_isolation` v1 reads stack shape only | a runner-side network policy, not a gate |
| `out/traces.db` | not needed until traces exist | trace work |

## 5. Next

1. Commit `compose.yaml` in `../mamute` and `../Online_Study_System`, then
   `make pin` both, then run `functional_parity` on a pristine run — that
   is the "self-check must be green" milestone and the first real proof the
   gate reproduces the goldens.
2. Author `openclinica/compose.yaml` (postgres + liquibase + tomcat) and
   re-pin; switch its `db` binding from `shell@1` to `postgres@1`.
3. Trace capture adapter + oracle contract for `trace_similarity`.
4. Add `oneshot_decoupling` manifests (they resolve cases by discovery, so
   a seed row is all that is needed).
