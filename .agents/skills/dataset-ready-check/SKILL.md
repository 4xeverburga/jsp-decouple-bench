---
name: dataset-ready-check
description: >
  Validate that a sample is ready for release in this benchmark: it boots
  from a fresh clone at its pinned commit, the no-op self-check reproduces
  the goldens while isolation still fails, the gates are sensitive to real
  breakage, results are deterministic, the agent cannot see the answer key,
  at least one controller is fully covered, and the OpenTelemetry agent
  produces a usable trace base for `trace_similarity`. Use when asked to
  "check if this sample is dataset ready", "validate the sample", or "is
  this sample ready to publish".
---

# Dataset-ready check for a sample

> **Partly stale.** The commands below (`make db-init`, `make task`,
> `make gate`, `bench.db`, `SAMPLE_SANDBOX`, `HARNESS_CMD`) are retired —
> `main.py` is the command line and `specs/` is the source of truth. The
> `network_isolation` checks describe a gate that no longer exists.

Run this against ONE sample (slug from `bench.db`). Every check must pass;
a sample that fails any check is not publishable, because every agent
score produced on it would be meaningless. Write the result to
`out/ready/<sample>.md` (`out/` is gitignored).

**Prerequisites:** `prepare-repo-for-dataset` is done (history protected,
runnable, OTel agent installed) and the cases were authored with
`test-slice`.

## Commands under test

```bash
make db-init
make task MANIFEST_ID=<n> SAMPLE_SANDBOX=<abs empty folder> \
          HARNESS=command HARNESS_CMD=true            # -> run_id
make gate GATE_ID=functional_parity  RUN_ID=<run_id>
make gate GATE_ID=network_isolation  RUN_ID=<run_id>
make gate GATE_ID=trace_similarity   RUN_ID=<run_id>
```

`SAMPLE_SANDBOX` is an absolute folder that exists for that one run and
holds nothing yet. The bench clones the pin into it from the local mirror
`out/cache/<slug>.git` and refuses a folder with anything in it, so no
sibling tree exists for an agent to read — the checks cannot disturb a
working copy and nothing can be learned by looking around the sandbox.

## Checks (in order — stop at the first hard failure)

### 1. The pinned commit boots from scratch
- `SAMPLE.commit_sha` contains `SAMPLE.entrypoint` (`compose.yaml`), its
  `Dockerfile` and `.env`. The runner refuses otherwise.
- The sample's `.env` is tracked and holds only synthetic credentials;
  `.env.example` documents every variable. No real secrets anywhere
  (grep for tokens/keys).
- `docker compose down -v` then a `functional_parity` gate run (it
  starts the stack itself): healthchecks go green with no network beyond
  the first image pull. Record the cold-start time; > 15 min is a
  usability problem.
- `grep -rE '/home/|/usr/lib/jvm' compose.yaml Dockerfile .env* scripts/`
  is empty. Only docker + make are needed on the host.
- The scoring stack is the bench's (`src/samples/<slug>/env/`) and the
  pin carries no compose file — `solves.materialise` refuses one. The old
  shape check (`front`/`db`, networks `api`/`data`) died with
  `network_isolation`.

### 2. No-op self-check (the most important check)
The two gates must **disagree** on an untouched tree, and that
disagreement is the whole point: parity proves the golden is
reproducible, isolation proves the task is still undone.
- A `HARNESS=command HARNESS_CMD=true` run must have `diff_empty: true`
  in `out/runs/<run_id>/harness.json`.
- `functional_parity` must be `pass`, `value 1.0`, for **every** manifest
  of the sample.
- `network_isolation` must **fail**, on the `front:isolated_from_db`
  sub-check: the pinned `front` still shares `data` with `db`. A `pass`
  here means the sample ships pre-decoupled and grades nothing — re-pin
  to the monolithic shape (see `prepare-repo-for-dataset`).
- If parity fails on an untouched tree, **the sample, the environment or
  the golden is wrong, not an agent**. Fix the cause (pinning, seed,
  flow) — never loosen a comparison or an `ignore_columns` list to pass.

### 3. Sensitivity — the gate must be able to fail
A gate that cannot fail proves nothing.
- Run a task with a harness command that breaks a covered controller
  in the fresh clone (e.g. `HARNESS_CMD="sed -i 's/…/…/' <Controller>.java"`).
  `functional_parity` must report `fail` for the cases that exercise it.
- Flip one byte of a case's `expect.json`: that case must fail. Restore
  with `git checkout -- <file>` and confirm `git diff --exit-code` is
  clean.
- **Isolation must be sensitive in both directions**, but only one of
  them is cheap to confirm.
  - *Fails when it should*: in the fresh clone, add a `ports:` entry to
    `db` and re-run — isolation must fail. Then give `front`
    `network_mode: host` and confirm it fails again. Restore with
    `git checkout -- compose.yaml`.
  - *Passes when it should*: remove `data` from `front.networks` in the
    clone and re-run — isolation must go `pass` at once, because it reads
    declarations and nothing has to boot. Parity is a separate
    measurement: an app that no longer reaches the database fails
    `functional_parity`, not isolation. Restore with
    `git checkout -- compose.yaml`.
  - A `pass` on the pristine pin is not sensitivity: it means the sample
    ships pre-decoupled (check 2). Re-pin instead.

### 4. Determinism
- Repeat check 2 **twice** on fresh stacks: every case result identical
  (`diff` the `cases/*.json` of both runs).
- Repeat `make case-capture` for one case per slice:
  `git diff --exit-code src/gates/functional_parity/cases/<sample>/` is
  clean. Fix flakiness by pinning (seed, clock, locale), never by
  loosening.
- `en-US`, `UTC`, `1280x800` come from `config.py`; nothing in a flow
  depends on host time or locale.

### 5. The agent cannot see the answer key
- The sample checkout contains none of: `expect.json`, `case.json`,
  `bench.db`, `seeds/`, case names, and no benchmark vocabulary
  (`benchmark`, `golden`, `parity`, `baseline`, `evaluation`, `BENCH_`
  outside `compose.yaml` port variables):
  `git grep -iE 'golden|parity|baseline|benchmark|expect\.json'` is empty
  on the pinned commit.
- **The checkout does not point at its own origin.** Provenance lives in
  `SAMPLE.project_id`, in `seeds/sources.json` and in the remote history,
  never in the tree: `UPSTREAM.md` is absent, and
  `git grep -InE 'github\.com/<owner>|upstream|@<upstream-domain>'` is
  empty apart from `LICENSE`, code namespaces (`br.com.<owner>.*`) and
  rendered product branding that the goldens already freeze. A sample
  that names its upstream hands the agent the original project to read.
- Every manifest `prompt` reads as a ticket: no routes, case names,
  expected DB deltas, or the words above. (`AGENTS.md` rules 2–3.)
- Credentials are read from `.env`, never hardcoded in a flow or prompt.

### 6. Registry, cases and coverage
- `make db-init && make samples && make manifests` list the sample with
  its pin and one manifest per slice; every `scope.cases` entry has
  `case.json`, `flow.py`, `expect.json` and `images/` on disk.
- Case names follow `<slice>__<behavior>`; each case has a db contract
  with explicit `ignore_columns` and `notes`.
- **Controller coverage:** every slice meets the `test-slice` rule —
  at least one controller fully covered — and the manifest's
  `scope.covers` entry matches the JaCoCo evidence (see `test-slice`
  §Coverage). Re-measure rather than trusting the recorded claim for the
  slice you are reviewing.

### 7. OpenTelemetry trace base (for `trace_similarity`)
`trace_similarity` compares the traces of a finished run against a base
taken from the pristine app, so the sample must emit a stable one.
- The app container starts with the OTel Java agent attached
  (`docker compose exec <service> ps -ef | grep javaagent` — `front` at
  the pin, both `front` and `back` after the split — or the JVM flags in
  `docker inspect`); jar version pinned, checksum verified in the image
  build, no download at boot.
- Config comes only from `OTEL_*` variables in the sample's `.env`
  (`OTEL_SERVICE_NAME=<slug>`, sampler `always_on`, metrics and logs
  exporters `none`). Any collector/sidecar is **declared in
  `compose.yaml`**, attached to `api` or `data` and publishing no port,
  so `front:networks` stays the gate's only failing sub-check (check 2).
- The app boots and passes its healthcheck with the collector stopped
  (the agent fails open; a missing collector must not break the sample).
- Attaching the agent changes no behaviour: check 2 is green **with the
  agent on**, same case results as without it.
- Replaying one case's flow yields spans for the server request, the
  covered controller's handler methods, the DB calls and, where the flow
  renders a JSP, the render. Run the flow twice: the span **tree shape**
  (names, parentage, `http.method`/route attributes) is identical; only
  ids and timestamps differ.
- Until the trace adapter exists, `trace_similarity` correctly reports
  `pending` / exit 3 (ROADMAP §2.3). Record the span evidence in the
  report instead of a gate verdict; once the adapter lands, the gate must
  move off `pending` on a no-op run.

### 8. Docs
- The sample's `AGENTS.md` runbook is copy-paste correct: build → boot →
  healthcheck on the pinned commit.
- `README.md` sample table lists it (stack, DB, entrypoint).

## Report format

```markdown
# Dataset-ready: <sample>

**Verdict:** READY | NOT-READY (<passed>/8)

| Check | Result | Notes |
|---|---|---|
| 1. Boots from scratch | pass/fail | cold start: X min |
| 2. No-op self-check | pass/fail | parity N/N pass, isolation fails as required |
| 3. Sensitivity | pass/fail | broken controller → parity fail; `front` off `data` → isolation pass |
| 4. Determinism | pass/fail | 2 runs, recapture clean |
| 5. Answer key hidden | pass/fail | |
| 6. Registry, cases, coverage | pass/fail | <controller>: methods N/N |
| 7. OTel trace base | pass/fail | spans/case, tree stable |
| 8. Docs | pass/fail | |
```

## Anti-goals

- Do NOT loosen a comparison, an `ignore_columns` list or a threshold to
  make check 2 or 4 pass — fix the root cause.
- Do NOT accept "works on my machine" — check 1 uses a fresh clone.
- Do NOT publish a sample whose no-op self-check is red or whose gates
  cannot fail (check 3).
- Do NOT make a no-op run pass `network_isolation`. A sample whose pin
  already keeps `front` off `data` has no task left in it; re-pin to the
  monolithic shape instead of accepting the vacuous pass.
- Do NOT treat `trace_similarity: pending` as a pass or a fail: it is
  neither; check 7 verifies the evidence the gate will need.
