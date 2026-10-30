---
name: authoring-bench-tests
description: >
  Principles and review checklist for the cases of a sample in this
  benchmark: self-containment, per-sample env, the DB delta pattern,
  Playwright determinism, and what makes a case tamper-proof. Use when
  reviewing or writing `case.json` / `flow.py`, or when a case is flaky.
  The step-by-step procedure for adding a case is `test-slice`.
---

# Authoring bench tests — principles

A case is a *functional-parity test*: `case.json` + `flow.py` + the golden
`expect.json`, under `src/samples/<sample>/cases/<slice>__<behavior>/`. A bad
case poisons every agent score run against it. This skill is the "why and
what good looks like"; **`test-slice` is the "how"** (procedure, capture,
manifest wiring). `dataset-ready-check` rejects samples that deviate.

**Prerequisite — `prepare-repo-for-dataset`:** the sample must already be
history-protected, runnable on its legacy toolchain, and pinned
(`sample.commit_sha` in `seeds/sources.json`). Authoring on an unprepared
repo bakes dependency drift into the goldens.

## Self-containment & per-sample env

Every case must run green on a freshly started stack with **no memory of
any previous run, manual session, or sibling case**.

- **No state carryover**: the flow performs a real login every run. Never
  replay cookies or assume a logged-in browser.
- **Credentials come from the sample's `env/.env`, never from the case**:
  the sample tracks `src/samples/<slug>/env/.env.example` (every variable
  the flows need) beside a `src/samples/<slug>/env/.env` of synthetic,
  deterministic values, so a stack boots identically for every researcher.
  The `.env` lives in the **bench**, never in the sample tree; `main.py
  capture` and `main.py score` read it and inject it into the process
  environment. Flows read `os.environ` only — never a literal password in
  `case.json`, `flow.py` or a prompt. **Real secrets (OAuth keys, API
  tokens) never go in a tracked `.env`.**
- **Fresh DB per case, structurally**: the scorer starts one stack per
  case and removes it (`src/bench/stack.py`), so `requires_db_reset` is a
  statement about the *design*, not a step anyone performs. Ids are stable
  because every boot replays the same seed. A case never depends on rows
  left by another case.
- **Fixtures over leftovers**: if a case needs entities (users,
  questions), its own arrange steps create them in-flow.

## The delta pattern (db contract)

Never compare absolute dumps; compare **before → after deltas**
(`inserted`/`updated`/`deleted` per table) so seed data, auto-increment
offsets and unrelated rows cancel out.

- Declare `key_columns` per table (`DESCRIBE` in mysql, `\d` in psql —
  never guessed).
- Declare `ignore_columns` for every volatile column (timestamps,
  counters not asserted on, uuids). When unsure, ignore more — a missed
  volatile column is flakiness, a missed real column shows in review.
- Exclude auth plumbing (e.g. session tables) deliberately and explain
  why in `notes`.
- The snapshot client runs **inside the `db` service**, in the dialect
  the manifest names (`bindings.db.options.dialect`), so no driver, port
  or host credential is involved. Both engines are read into the same
  unaligned TSV shape (`tabular.py`), so the comparison is identical.
- Pick behaviours that **leave a DB fingerprint**; an expected-empty
  delta (e.g. a blocked action) is valid only when the DOM artifact
  carries the assertion — say so in `notes`.

## Flow determinism

`flow.py` is the single source of truth; `main.py capture` and the gate
both run it through the same code (`cases.drive`). Concrete patterns are
in `test-slice` §3; the invariants:

- `locale="en-US"`, `timezone_id="UTC"`, viewport `1280x800` — from
  `settings.py` (`.env`), never the host.
- Never `sleep()`: wait for the response or the element that proves the
  action landed; wait explicitly on submit navigations.
- Artifacts are **normalized** (`<script>/<style>` stripped, whitespace
  collapsed, volatile attributes removed) and compared by exact string:
  structure and text only, never class names or inline styles —
  decoupling legitimately changes markup.
- Fill every date/time input explicitly; legacy forms prefill "today".

## The golden is generated, never written

`expect.json` comes only from `uv run python main.py capture` on the pinned
commit — the command cuts the tree itself, so the worktree you author in
cannot leak into the golden. The table specs inside it come from the
hand-written `case.json`, the values from the run. Hand-edited goldens
drift from reality. If a case fails on an untouched tree, re-capture from
the pristine app *and understand why it differed* before accepting the new
golden.

## Review checklist (every case must satisfy)

- [ ] Deterministic: a second capture changes `captured_at` and nothing
      else (`git diff -U0 … | grep '^[+-]' | grep -v captured_at` is empty).
- [ ] Isolated: passes alone and after any other case (the scorer gives
      every case its own stack).
- [ ] Minimal: asserts the behaviour's observable effect, nothing more;
      a case dumping 40 tables is unmaintainable.
- [ ] No sleeps, no absolute paths, no network beyond the sample's stack.
- [ ] Timeouts from `settings`, never `timeout=5000` literals.
- [ ] Credentials from `os.environ` only.
- [ ] Named `<slice>__<behavior>`; listed in its manifest `scope.cases`.
- [ ] `locale`, `timezone_id`, `viewport` present in `case.json`.
- [ ] Every declared table is one the flow actually touches; and no table
      the flow touches is missing from `db.tables`.
- [ ] Contributes to the slice's controller coverage (`test-slice`).

## Anti-patterns

- Hand-editing `expect.json` to make a failing case pass.
- Asserting CSS classes or inline styles.
- One giant flow testing five behaviours — split per behaviour; that is
  what makes verdicts diagnosable.
- Cases that depend on execution order or on another case's leftovers.
- Putting routes, case names or goldens anywhere an agent can read them
  (the sample repo, a prompt) — `AGENTS.md` rules 1–3.
