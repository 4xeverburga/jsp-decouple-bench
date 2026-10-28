---
name: dataset-ready-check
description: >
  Validate that a sample is ready for release in this benchmark: it boots
  from a fresh clone at its pinned commit, the no-op self-check is green,
  the gates are sensitive to real breakage, results are deterministic, the
  agent cannot see the answer key, at least one controller is fully
  covered, and the OpenTelemetry agent produces a usable trace base for
  `trace_similarity`. Use when asked to "check if this sample is dataset
  ready", "validate the sample", or "is this sample ready to publish".
---

# Dataset-ready check for a sample

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
make pin  SAMPLE=<slug> SAMPLE_LOCATION=<fresh clone>
make task SAMPLE=<slug> TASK=<slice> SAMPLE_LOCATION=<fresh clone> \
          HARNESS=command HARNESS_CMD=true            # -> run_id
make gate GATE_ID=functional_parity  RUN_ID=<run_id>
make gate GATE_ID=network_isolation  RUN_ID=<run_id>
make gate GATE_ID=trace_similarity   RUN_ID=<run_id>
```

Always use a **fresh clone** of the sample as `SAMPLE_LOCATION`
(`git clone ../<sample> /tmp/<sample>-ready`). It proves a bare checkout
works, and keeps destructive checks off the real working tree.

## Checks (in order — stop at the first hard failure)

### 1. The pinned commit boots from scratch
- `SAMPLE.commit_sha` contains `SAMPLE.entrypoint` (`compose.yaml`), its
  `Dockerfile` and `.env`. The runner refuses otherwise.
- The sample's `.env` is tracked and holds only synthetic credentials;
  `.env.example` documents every variable. No real secrets anywhere
  (grep for tokens/keys).
- `docker compose down -v` then a gate run (it starts the stack itself):
  healthchecks go green with no network beyond the first image pull.
  Record the cold-start time; > 15 min is a usability problem.
- `grep -rE '/home/|/usr/lib/jvm' compose.yaml Dockerfile .env* scripts/`
  is empty. Only docker + make are needed on the host.

### 2. No-op self-check (the most important check)
- A `HARNESS=command HARNESS_CMD=true` run must have `diff_empty: true`
  in `out/runs/<run_id>/harness.json`.
- `functional_parity` must be `pass`, `value 1.0`, for **every** manifest
  of the sample. `network_isolation` must be `pass`.
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
  (`docker compose exec app ps -ef | grep javaagent` or the JVM flags in
  `docker inspect`); jar version pinned, checksum verified in the image
  build, no download at boot.
- Config comes only from `OTEL_*` variables in the sample's `.env`
  (`OTEL_SERVICE_NAME=<slug>`, sampler `always_on`, metrics and logs
  exporters `none`). Any collector/sidecar is **declared in
  `compose.yaml`**, so `network_isolation` still passes (check 2).
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
| 2. No-op self-check | pass/fail | parity N/N, isolation pass |
| 3. Sensitivity | pass/fail | broken controller → fail |
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
- Do NOT treat `trace_similarity: pending` as a pass or a fail: it is
  neither; check 7 verifies the evidence the gate will need.
