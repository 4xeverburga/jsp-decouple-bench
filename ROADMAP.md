# ROADMAP

What is done, what is next, and what is parked. Decisions of record live in
`specs/`; this file is only direction.

## Next

1. **Close the answer-key leak.** This repository is public and tracks every
   `expect.json` and `trace.json`, and the solve sandbox (`solve.yaml`) is on
   the default bridge, with internet egress: an agent can clone the goldens.
   Until one of the two is closed (a private repository, or a solve network
   with no route out but the package mirrors it needs), a score is only as
   good as the trace audit that shows the agent did not fetch them.
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

## Done

- A solve is kept as its pin and its diff, never its tree: `score` rebuilds
  the tree under `out/scratch/`, refuses one whose digest is not the
  record's, and refuses a manifest whose sample or name are not the ones
  the run was solved for. `out/` went from 4.2 GB to about 0.5 GB.
- Capture never runs git over the agent's `.git`: the checkout is copied
  into the bench's own baseline without it.
- Pins carry no `.dockerignore`; the bench keeps it as
  `Containerfile.dockerignore`, and one multi-stage `Containerfile` per
  sample builds both images (`toolbox` for the solve, `app` for scoring).
- Solve toolboxes carry the sample's Maven cache (`~/.m2`), built from the
  tree the agent gets but never reading it: the checkout is bind-mounted over
  `/workspace`, so a solve starts with a warm cache instead of paying the
  cold download in the agent's own time.
- Inspect-based bench; `main.py` is the whole command line.
- `trace_similarity`: the score phase replays each case once
  (`src/bench/replay.py`) and both gates judge that run; spans are
  condensed to a request tree, a tree with no hop fails outright, and a
  judge from `tasks-config.yaml`'s `score_profiles` rules on the rest
  against the case's `trace.json`. Bases are captured for all three
  samples.
- Golden capture is a command again: `main.py capture` cuts the pin, runs
  one stack per case, and writes `expect.json`.
- `functional_parity` reads any SQL dialect the manifest names (`mysql`,
  `postgres`), from inside the case's `db` service.
- Three samples with a scoring stack: `mamute` (Jetty + MySQL),
  `openclinica` (Tomcat 9 + PostgreSQL 9.6) and `online-study-system`
  (Tomcat 9 + MySQL 5.7, the tree's own dump as the seed), all under the OTel
  agent, each with a `dummy_file` manifest for cost-free end-to-end checks.
- `.agents/skills/` describe `main.py` and the current sample layout.
- Work orders with no docker, compose or container vocabulary.
- Scoring driven from the host: one compose project per case.
- `network_isolation` retired: with one scoring service there is no network
  contract left to grade.
- Solve is agent-agnostic: a `tasks-config.yaml` solve profile (`--profile`)
  selects native ReAct or a registered CLI agent, and the model that answers
  it.
- `templates/` deleted: the stack lives in `src/samples/<slug>/env/`, so
  there is no compose to copy into a pin — and a pin that carries one is
  refused at the first solve.
