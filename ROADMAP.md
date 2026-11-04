# ROADMAP

What is done, what is next, and what is parked. Decisions of record live in
`specs/`; this file is only direction.

## Next

1. **`trace_similarity`, beyond mamute.** The scorer is built (a
   deterministic floor, then a judge from a `score_profiles` entry) and the
   mamute cases have their `trace.json`. Remaining:
   - capture bases for `openclinica` and add the scorer to manifest 13;
     its condensed tree has not been looked at yet;
   - calibrate the judge: the same verdicts from two `score_profiles` on
     the same trees, and a few doctored trees (a write left on the page
     side, a hop that only reads) per sample before a verdict is quoted;
   - list controller and DAO methods in `OTEL_INSTRUMENTATION_METHODS_INCLUDE`
     if a case needs to see in-process calls, not just their SQL.
2. **A full task end to end** on a real agent, then `audit-agent-trace`
   before any score is quoted. **Only one combination has ever finished a
   run here: `opencode` 1.19.5, answered by
   `opencode-go/deepseek-v4.1-flash`.** Nothing else is proven — not
   another OpenCode model, not another agent.
3. **Prove the other CLI agents.** `src/agents/registry.py` registers `opencode`,
   `codex`, `claude` and `gemini`, and a profile's `agent` selects one, but only
   `opencode` has run. 
   
# Parked
- **One phase instead of two.** Scoring no longer needs an Inspect sandbox, so
  solve and score could run in a single task. Kept apart for now because a kept
  tree can be re-graded without paying for the agent again.
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
  wiring rather than on logic: a separate toolbox image, Node 20 beside the
  grunt-era 16, the EOL-bullseye apt traps, roughly +500 MB per solve
  build.

## Done

- Solve toolboxes carry the sample's Maven cache (`~/.m2`), built from the
  tree the agent gets but never reading it: the checkout is bind-mounted over
  `/workspace`, so a solve starts with a warm cache instead of paying the
  cold download in the agent's own time.
- Inspect-based bench; `main.py` is the whole command line.
- `trace_similarity`: the score phase replays each case once
  (`src/bench/replay.py`) and both gates judge that run; spans are
  condensed to a request tree, a tree with no hop fails outright, and a
  judge from `tasks-config.yaml`'s `score_profiles` rules on the rest
  against the case's `trace.json`. `runs.yaml` became `tasks-config.yaml`
  (`solve_profiles`, `score_profiles`).
- Golden capture is a command again: `main.py capture` cuts the pin, runs
  one stack per case, and writes `expect.json`.
- `functional_parity` reads any SQL dialect the manifest names (`mysql`,
  `postgres`), from inside the case's `db` service.
- Three samples with a scoring stack: `mamute` (Jetty + MySQL),
  `openclinica` (Tomcat 9 + PostgreSQL 9.6) and `online-study-system`
  (Tomcat 9 + MySQL 5.7, the tree's own dump as the seed), all under the OTel
  agent. `online-study-system` has its eleven cases captured with a
  `trace.json` each, and manifests 5-12 grade them against
  `functional_parity` and `trace_similarity`.
- `.agents/skills/` describe `main.py` and the current sample layout.
- Samples under `src/samples/<slug>/{cases,env}`.
- Work orders with no docker, compose or container vocabulary.
- Scoring driven from the host: one compose project per case.
- OpenTelemetry in the mamute stack.
- `network_isolation` retired: with one scoring service there is no network
  contract left to grade.
- Solve is agent-agnostic: a `tasks-config.yaml` solve profile (`--profile`) selects
  native ReAct or a registered CLI agent, and the model that answers it. Only `opencode`
  is verified end to end (see Next 2 and 3).
- `templates/` deleted: the stack lives in `src/samples/<slug>/env/`, so
  there is no compose to copy into a pin — and a pin that carries one is
  refused at the first solve.
