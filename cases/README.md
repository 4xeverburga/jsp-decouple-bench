# `cases/` — the behaviour corpus

Frozen golden data, one directory per case: `<sample>/<slice>__<behavior>/`.

- `case.json` — hand-written contract: e2e (routes, locale, timezone,
  viewport, credentials source, artifacts) + db (tables, key columns,
  ignored columns, notes).
- `flow.py` — the Playwright flow. Single source of truth for the behaviour.
- `expect.json` — the golden. **Generated** by `make case-capture` from the
  pristine checkout; never hand-edited.
- `images/` — step screenshots from the golden capture. Review evidence
  only; never compared by a gate.

Read by `src/run/context.py` (accessors), the `functional_parity` gate,
the `oneshot_decoupling` task and `main.py case capture`. `TASK_MANIFEST.
scope_json` names which cases a run is graded against.

This directory is **data, not code** — it stays out of `src/` on purpose.
See `specs/modules.md` §"Who owns the corpus" for the dependency rule, and
`.agents/skills/test-slice/SKILL.md` for how to add a case.
