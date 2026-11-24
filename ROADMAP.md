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

   These targets grade the cases, never an agent: they read the pin's
   code, out of band, while a solve is judged only on its side effects.
   A manifest is done when:
   - **handlers**: every slice handler is driven by a case, or excused in
     `not_driven` — 100%;
   - **slice branches**: every branch is driven by a case, or *omitted*
     with its reason — 100% accounted for. A branch is omitted only when
     the app cannot reach it from a state it produces itself: through its
     own UI, from the dump plus legitimate seed rows. A defensive null
     check on an orphaned row, a `catch` for an infrastructure failure, or
     a server refusal the page's own script already prevents. Hard to
     reach is not a reason; a case is;
   - **mutation** (once metric 3 exists): at least 80% of the
     non-equivalent mutants of the slice killed by parity, raised as the
     survivors are read. This is the number that is the cases' power;
     coverage only says where cases are missing.

   Lines get no target: they follow from branches.

   Rules for the work: an existing case and its golden are never edited;
   one may be deleted (git keeps it) once newer cases check everything it
   checks, final rows included. Every addition is a new case with its own
   `capture`, and the
   manifest's `version` is bumped so its earlier scores are not compared
   with the later ones. A branch that needs rows the dump lacks gets a
   new case that carries its own seed, loaded once on that case's stack
   after the dump; no existing case and no shared dump changes. Re-run
   `coverage` after each capture and keep the report beside the commit.

   By manifest, highest yield first:
   - **`vote-flow`** — done in version 5: 4/4 handlers, slice lines 100%
     (was 50%), controller lines 80% (was 43%). New cases remove an
     upvote, remove a downvote, and switch an upvote to a downvote; each
     reloads the page between the two clicks, so the highlighted arrow
     comes from the stored vote, not from the widget. Omitted: the
     controller's two `catch → 409` blocks and the karma gate's 403,
     which `links-behaviour.js` refuses before any request leaves the
     page (author's own question, karma below `permission.rule.vote_*`).
     Left for the per-case seed: a fifth downvote, which hides the
     question (`VotingMachine.register`, count ≤ -5) and needs five
     voters with the karma for it.
   - **`answer-flow`** — done in version 7: `AnswerController` slice
     lines 95%, branches 4/6 by the report's per-line lower bound, 5/6
     in fact (`watching` is false in one case and true in the others).
     New cases: a second answer submitted from a stale tab and refused,
     an answer with `watching` cleared, the author's own question with
     the form withheld for karma, and the moderator answering its own
     question through the same-author confirmation. A fresh page
     withholds the form from both `AnsweredByValidator` refusals
     (`canAnswer.tag`); only the stale tab reaches the server's. Left for
     the per-case seed: `isUserWithKarma` false, a user with negative
     karma. Omitted: the 403 of mamute's 15 s flood limit, whose message
     counts the seconds left.
   - **`subject-flow`** — version 5: `AddNewSubjectServlet` slice lines
     37% → 50%, branches 28% → 33% (lower bound). New cases: a duplicate
     person ID, a duplicate study subject ID, every field invalid in one
     submit, the required fields blank, "Save and Add Next Subject" and
     "Save and Assign Study Event". Most of what is left hangs on the
     study's parameters, which the admin sets through the app's own Build
     Study pages, so each is reachable: year of birth instead of date of
     birth, generated study subject IDs, a person ID not required, gender
     not required, a group class (required group, notes over 255), a site
     (the "enrolled at a site" refusals), a subject already in another
     study (`ADD_EXISTING_SUBJECT`), and `addWithEvent` from the list's
     overlay, which needs an event definition. Each is a new case,
     arranged through those pages or by a per-case seed.
   - **`exam-flow`** — add the two refusals of `startExam`: an exam
     before every period is studied, and a second exam on the same
     course.
   - **`select-course-flow`** — add selecting a course already selected
     or taken (`stuSelectedCourse`, the "已经选过或修过" error). The
     low-balance refusal is already a case.
   - **`teacher-mark-flow`** — add grading a student who has not taken
     the exam (`markUI` refuses it).
   - **`admin-student-flow`** — a list page other than the first
     (`showStudent?page=2`, which needs enough seeded rows). There is no
     "user name taken" refusal to grade: `addStudent` sets `userlogin` to
     `null` the line before it tests it, and `userlogin.name` has no
     unique key, so a taken name is simply added again. The branch is
     dead code; omitted.
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
   - a per-case seed: a `seed.sql` beside a case's `flow.py`, loaded by
     `capture`, `score` and `coverage` on that case's stack only. Needed by
     the `?page=2` cases and by `vote-flow`'s auto-removal;
   - omitted branches in `scope.covers`, keyed by the pin's source line,
     so the report reads covered / omitted / GAP per slice branch rather
     than a percentage;
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

