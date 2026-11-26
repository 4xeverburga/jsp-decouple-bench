# ROADMAP

What is done, what is next, and what is parked. Decisions of record live in
`specs/`; this file is only direction.

## Next

1. **Raise the power of the slice cases.** `main.py coverage` measured
   all twelve `decouple_slice` manifests against their slice
   (`out/coverage/<manifest>/report.md`, `src/controls/`). Every
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
     (`canAnswer.tag`); only the stale tab reaches the server's. Omitted:
     the 403 of mamute's 15 s flood limit, whose message counts the
     seconds left. Version 8 adds a seeded case, the moderator at karma -5
     answering (`hasKarma()` false: the answer is saved, no karma is
     added), and lists two ask-flow cases for `showQuestion`, the
     removed question and the upvote banner, so every slice branch is
     driven. No-op parity green; the coverage report is still to be
     re-run and committed.
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
   - **`exam-flow`** — done in version 5: slice lines 90% → 100%,
     branches 2/4 → 3/4 by the lower bound, 4/4 across cases: the
     `process != period` refusal is taken by the early exam, its other
     side by the two cases that reach the `hasExam` check below it. New
     cases: an exam before every period is studied, and a second exam
     from the list `saveExam` renders, which still offers 考试 for the
     examined course.
   - **`select-course-flow`** — version 5 adds selecting a course
     already selected: slice lines 89% → 93%, branches 3/6 by the lower
     bound, 5/6 across cases. Version 6 adds a seeded course priced 0:
     enrolment is written, the student row is not, so all six branches
     are driven across cases. A mutant of that `if` is equivalent by side
     effects (writing an unchanged balance leaves the same row), so this
     case adds coverage, not kill power, on that line.
   - **`teacher-mark-flow`** — done in version 5: grading a student who
     studied every period but took no exam, which the grade page offers
     (it checks progress, not the exam) and `markUI` refuses. Slice lines
     88% → 94%; branches 2/4 by the lower bound, 3/4 across cases.
     Omitted: `gradeCourse` without an `id`, which no page links to.
   - **`admin-student-flow`** — version 5: slice branches 6/10 → 9/10,
     lines 91% → 97%. The pager's 最后一页 and 上一页 links on a
     one-page list send page=1 and page=0, which drive both other sides
     of `page == null || page == 0`. Omitted: `addStudent`'s "name taken"
     check, dead code (`userlogin` is set to `null` the line before it is
     tested, and `userlogin.name` has no unique key). Version 6 adds a
     seeded case: nine students past the dump's three, so page 2 lists
     two rows at a real offset. Coverage does not move, but a tree whose
     student paging ignores the offset now fails (checked: `limit 0`
     fails only this case).
   - **`study-flow`** — done in version 5: going back from the first
     period and forward past the last, where progress does not move.
     Branches 2/4 → 3/4 by the lower bound, 4/4 across cases.
   - **`admin-course-flow`** — done in version 5: slice branches 1/4 →
     4/4, lines 88% → 100%, by the same pager links. Version 6 adds the
     first seeded case: eight courses past the dump's four, so page 2
     lists two rows at a real offset (`limit 10, 10`). Coverage does not
     move — the branches were already driven — but a tree that ignores
     `page` now fails; mutation testing is what will count it.
   - **`ask-flow`** — done in version 5: slice lines 98% → 100%,
     branches 3/6 → 4/6 by the report's lower bound (both sides of
     `isVisibleFor` and of `watching` are driven across cases). New
     cases: a question with `watching` cleared, a new tag with illegal
     characters refused by `TagsValidator` (the picker offers any typed
     term), and a question removed by a moderator's flag, which a
     logged-out visitor gets as not found. Version 6 adds the other side
     of `!isVotingEnough()`: a seed backdates the moderator's
     `lastUpvote`, and the question page asks it for an upvote. Every
     slice branch is driven; no-op parity green.
   - **`watch-flow`** — version 5 adds unwatching (watch, reload,
     click the eye). Still 100% of a 7-line controller: the toggle's two
     sides live in `WatcherDAO.addOrRemove`, which the instrument does
     not measure yet.
   - **`out-course-flow`**, **`recharge-flow`** — what they miss is a
     `catch` and a null check the UI cannot reach; leave as they are.
     Both meet the bar: handlers 100%, and recharge's one gap
     (`student != null`) is omitted.
   - **`admin-teacher-flow`** (manifest 23, new) — `AdminController`'s
     seven teacher handlers, nine cases: add, a taken name refused, edit,
     edit of a teacher removed in another tab (not found), remove, remove
     refused while the teacher has courses, search, the single-page pager
     and a seeded second page. All nine captured; the no-op score
     (determinism), the coverage report and a sensitivity check are still
     to run before it is used for a solve. Next candidates from the same
     controller: course edit/remove/search, student edit/search, as new
     manifests so the scored ones stay comparable.

   Read the reports' slice branches as a lower bound: JaCoCo's line
   counts do not say which side a case took, so two cases taking
   opposite sides each read 1/2. `exam-flow` is 4/4 across cases.

   The instrument itself, in the same order:
   - ~~a per-case seed~~ — done: a `seed.sql` beside a case's `flow.py`,
     loaded by `observe.arrange` on that case's stack only, after the
     stack is ready and before the first snapshot; the golden pins its
     `seed_sha256`. Users: `admin-course-flow` v6, `admin-student-flow`
     v6, `select-course-flow` v6, `ask-flow` v6, `answer-flow` v8. A seed
     may also update a row the app made, when a real user reaches that
     state without help (a moderator idle for a week, or downvoted below
     zero). mamute's first-boot moderator is `Users.id` 1001, not 1. Still
     to write: `vote-flow`'s auto-removal;
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
     if a case needs to see in-process calls, not just their SQL;
   - a known false negative of `judge-deepseek-flash-high`: it fails a
     tree whose backend drops a duplicate read (`SQL SELECT course x2` in
     the base, once in the backend) as if a read stayed on the page side.
     Seen twice: Kimi's `study-flow` run `e264b983`
     (`next-past-last-period-stays`) and DeepSeek's `exam-flow` run
     `4cb831c8` (`save-exam-marks-has-exam`). Re-judge both with
     `judge-claude-opus-5.5-high` before quoting a trace verdict, and
     tell the judge that fewer reads is not a crossed boundary.
3. **Re-score every run scored before the port fix.** Until then a
   scoring stack listened on 8080 inside and a free port outside, so a
   self-call built from the request's address (`getServerPort()`, the
   `Host` header, which most agents use) hit a dead port. DeepSeek's
   `exam-flow` run `4cb831c8` went from 0 to parity 3/3 on re-score, and
   both Kimi `admin-course-flow` runs from 0/3 to 3/3. Every earlier
   score is suspect until re-scored: the Tomcat samples were fixed in
   6fa9e62, mamute (Jetty, which had the same mismatch) after it. Five of
   DeepSeek's six mamute trees self-call through `getServerPort()` or the
   `Host` header.
4. **Kimi K3.1 Pro against DeepSeek V4.1 Flash, react agent.** Same
   agent, provider and window; Kimi at `medium`, DeepSeek at `high`.
   Scored so far (DeepSeek judge): `admin-course-flow` Kimi 3/3;
   `study-flow` both parity 4/4, Kimi trace 3/4 (the false negative
   above); `teacher-mark-flow` both 2/2; `admin-student-flow` v6 Kimi
   parity 3/4, DeepSeek 4/4. Kimi's tree round-trips the legacy
   `PagingVO` through JSON, and its `setTotalCount` turns the page count
   back into a row count, so 12 students show one page. DeepSeek took
   about twice the time and tokens. Open: fresh DeepSeek solves of the
   slices it failed before (`exam`, `ask`, `answer`, `vote`, `watch`) and
   Kimi on the same, re-judged with the Opus judge, two or three runs a
   slice before a model is called stronger.
5. **Prove the other CLI agents.** `opencode` 1.19.5 (DeepSeek V4.1 Flash,
   GLM 5.3 Flash), `claude` 2.1.311 (Opus 5.5, Sonnet 5.5) and native `react`
   have finished solves here; `codex` and `gemini` are registered in
   `src/harness/agents/registry.py` and have never run.

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

