# ROADMAP

What is done, what is next, and what is parked. Decisions of record live in
`specs/`; this file is only direction.

## Next

1. **Raise the power of the slice cases.** `main.py coverage` measured
   all twelve `decouple_slice` manifests against their slice
   (`out/coverage/<manifest>/report.md`, `src/bench_controls/`). Every
   slice handler is driven except two, and slice lines sit above 85%
   almost everywhere, but slice branches stop at 25–60%: the cases walk
   the happy path, and the refusals and validation errors that guard each
   write never run. An agent can break any of them and still pass.
   A refusal case is cheap to grade: parity already sees an empty row
   delta and the message on the page.

   Rules for the work: existing cases and their goldens stay as they
   are; every addition is a new case with its own `capture`, and the
   manifest's `version` is bumped so its earlier scores are not compared
   with the later ones. Re-run `coverage` after each capture and keep the
   report beside the commit.

   By manifest, highest yield first:
   - **`vote-flow`** — 2/4 handlers. Add removing an upvote and removing
     a downvote (clicking the same arrow again): `voteUpRemoval` and
     `voteDownRemoval` have no case at all.
   - **`answer-flow`** — its own prompt requires "a rejected answer shown
     the same way", and no case rejects one: the validator's error
     redirect (`newAnswer`, lines 103–104) never runs.
     `AnsweredByValidator` rejects two things: a second answer from the
     same user, and an answer to one's own question without the karma
     for it. Add both; then an answer posted with `watching` unchecked.
   - **`subject-flow`** — `AddNewSubjectServlet.processRequest` is ~400
     lines and its one case runs 37%. Add a duplicate person ID (the
     "already enrolled" errors), a missing required field, and an invalid
     date or year of birth; then adding with `addWithEvent`.
   - **`exam-flow`** — add the two refusals of `startExam`: an exam
     before every period is studied, and a second exam on the same
     course.
   - **`select-course-flow`** — add selecting a course already selected
     or taken (`stuSelectedCourse`, the "已经选过或修过" error). The
     low-balance refusal is already a case.
   - **`teacher-mark-flow`** — add grading a student who has not taken
     the exam (`markUI` refuses it).
   - **`admin-student-flow`** — add a student whose user name is taken
     (`addStudent` throws before writing); then a list page other than the
     first (`showStudent?page=2`, which needs enough seeded rows).
   - **`study-flow`** — add both edges: going back from the first period
     and forward past the last, where progress must not move.
   - **`admin-course-flow`** — 1/4 slice branches: add a list page other
     than the first (`showCourse?page=2`).
   - **`ask-flow`** — add a question asked with `watching` unchecked, and
     a question page the viewer may not see (`showQuestion` →
     `notFound`).
   - **`watch-flow`** — 100% of a 7-line controller, which says little:
     the toggle lives below it. Add unwatching (the prompt names it), and
     measure the DAO, not only the controller.
   - **`out-course-flow`**, **`recharge-flow`** — what they miss is a
     `catch` and a null check the UI cannot reach; leave as they are.

   The instrument itself, in the same order:
   - measure what a slice calls below the controller (service, DAO), so
     a thin controller like `WatchController` stops reading as covered;
   - `covers` for the `whole-app` manifests, which need several
     controllers each and a slice per route;
   - mutation testing (metric 3): coverage says a line ran, not that a
     case would fail if it were wrong. Mutate the slice's handlers in the
     pin, replay its cases, and count the mutants parity kills.

2. **Calibrate the `trace_similarity` judge.** Every sample now has its
   bases and the scorer on its flow manifests. Remaining:
   - the same verdicts from two `score_profiles` on the same trees, and a few
     doctored trees (a write left on the page side, a hop that only reads)
     per sample before a verdict is quoted;
   - list controller and DAO methods in `OTEL_INSTRUMENTATION_METHODS_INCLUDE`
     if a case needs to see in-process calls, not just their SQL.
3. **Prove the other CLI agents.** `opencode` 1.19.5 (DeepSeek V4.1 Flash,
   GLM 5.3 Flash), `claude` 2.1.311 (Opus 5.5, Sonnet 5.5) and native `react`
   have finished solves here; `codex` and `gemini` are registered in
   `src/agents/registry.py` and have never run.

## Parked

- **Manifest ids from a database.** A record names its manifest by id, and
  an id once came to mean another task: manifest 18 was `answer-flow-120`
  on mamute, was deleted, and its id was given to
  `whole-app-online-study-system`. `score` now refuses a manifest whose
  sample or name differ from the record's, so a reused id fails loudly
  instead of grading the wrong task. A SQLite table with `AUTOINCREMENT`
  would make reuse impossible, since it never hands out a deleted id
  again; but the manifests would stop being a reviewable text diff, and
  the bench's seeds are edited by hand and read in pull requests. Revisit
  if manifests start being created by tooling rather than by hand.
- **One phase instead of two.** Scoring no longer needs an Inspect sandbox, so
  solve and score could run in a single task. Kept apart for now because a
  kept solve can be re-graded without paying for the agent again.
- **App as native processes** (no Docker for scoring). Only worth it if the
  bench itself must run inside a container; costs the pinned toolchain.
- **A browser in the agent's toolbox — deliberately absent.** The solve
  sandbox has no Playwright, no Chromium and none of the libraries one needs
  (`libnss3`, `libatk`, `libgbm` are all missing), and its Node 16 is below
  the `>=20` that Playwright 1.63 declares, so the agent cannot install one
  either. The scorer's browser runs on the host and drives the published
  port; parity compares outcomes (`dom_*`, counts, the DB delta), never
  pixels, so a browser would add nothing to judging. What it costs the
  agent is the *wiring* check: the graded flows drive select2 and the
  `up-down-vote.js` widget, which `curl` cannot exercise, and the flow's
  `_normalize()` strips `<script>`/`<style>`, so a clean DOM diff does not
  prove the page still works. Revisit if failures cluster on broken AJAX
  wiring rather than on logic: Node 20 beside the grunt-era 16 in the
  `toolbox` target, the EOL-bullseye apt traps, roughly +500 MB per solve
  build.

