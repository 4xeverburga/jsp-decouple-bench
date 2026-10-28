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
`expect.json`, under
`src/gates/functional_parity/cases/<sample>/<slice>__<behavior>/`. A bad
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
- **Credentials come from the sample's `.env`, never from the case**: the
  sample tracks `.env.example` (every variable the flows need) and a
  `.env` of synthetic, deterministic bench values, so a bare checkout
  boots identically for every researcher. Flows read them from
  `os.environ` only — never a literal password in `case.json`, `flow.py`
  or a prompt. **Real secrets (OAuth keys, API tokens) never go in a
  tracked `.env`.**
- **Fresh DB per case**: `requires_db_reset: true`; ids are stable
  because every boot replays the same seed. A case never depends on rows
  left by another case.
- **Fixtures over leftovers**: if a case needs entities (users,
  questions), its own arrange steps create them in-flow.

## The delta pattern (db contract)

Never compare absolute dumps; compare **before → after deltas**
(`inserted`/`updated`/`deleted` per table) so seed data, auto-increment
offsets and unrelated rows cancel out.

- Declare `key_columns` per table (from `DESCRIBE`, not guessed).
- Declare `ignore_columns` for every volatile column (timestamps,
  counters not asserted on, uuids). When unsure, ignore more — a missed
  volatile column is flakiness, a missed real column shows in review.
- Exclude auth plumbing (e.g. session tables) deliberately and explain
  why in `notes`.
- The capture dump user observes only; the case never mutates the DB
  outside the flow.
- Normalize types in dumps (dates → ISO, decimals → strings) so the JSON
  comparison is stable.
- Pick behaviours that **leave a DB fingerprint**; an expected-empty
  delta (e.g. a blocked action) is valid only when the DOM artifact
  carries the assertion — say so in `notes`.

## Flow determinism

`flow.py` is the single source of truth; the gate and `case-capture` both
run it through the browser adapter. Concrete patterns are in `test-slice`
§3; the invariants:

- `locale="en-US"`, `timezone_id="UTC"`, viewport `1280x800` — from
  `config.py`, never the host.
- Never `sleep()`: wait for the response or the element that proves the
  action landed; wait explicitly on submit navigations.
- Artifacts are **normalized** (`<script>/<style>` stripped, whitespace
  collapsed, volatile attributes removed) and compared by exact string:
  structure and text only, never class names or inline styles —
  decoupling legitimately changes markup.
- Fill every date/time input explicitly; legacy forms prefill "today".

## The golden is generated, never written

`expect.json` comes only from `make case-capture` on a clean checkout at
the pinned commit. Hand-edited goldens drift from reality. If a case
fails on an untouched tree, re-capture from the pristine app *and
understand why it differed* before accepting the new golden.

## Review checklist (every case must satisfy)

- [ ] Deterministic: two captures give a byte-identical `expect.json`.
- [ ] Isolated: passes alone and after any other case (fresh DB each).
- [ ] Minimal: asserts the behaviour's observable effect, nothing more;
      a case dumping 40 tables is unmaintainable.
- [ ] No sleeps, no absolute paths, no network beyond the compose stack.
- [ ] Credentials from `os.environ` only.
- [ ] Named `<slice>__<behavior>`; listed in its manifest `scope.cases`.
- [ ] `locale`, `timezone_id`, `viewport` present in `case.json`.
- [ ] Contributes to the slice's controller coverage (`test-slice`).

## Anti-patterns

- Hand-editing `expect.json` to make a failing case pass.
- Asserting CSS classes or inline styles.
- One giant flow testing five behaviours — split per behaviour; that is
  what makes verdicts diagnosable.
- Cases that depend on execution order or on another case's leftovers.
- Putting routes, case names or goldens anywhere an agent can read them
  (the sample repo, a prompt) — `AGENTS.md` rules 1–3.
