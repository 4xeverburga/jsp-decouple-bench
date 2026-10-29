# ROADMAP

What is done, what is next, and what is parked. Decisions of record live in
`specs/`; this file is only direction.

## Next

1. **`trace_similarity` scorer.** The mamute stack already emits spans
   (Jetty server, JDBC, Hibernate, `HttpURLConnection` client) to the
   `traces` volume. Remaining:
   - read `/traces/traces.jsonl` while the case's stack is still up;
   - capture a per-case **trace base** from the pristine pin, frozen next to
     `expect.json`;
   - compare span-tree *shape* (names, parentage, `http.method`/route), not
     ids or timestamps, and tell a REST hop (client + server span) from an
     in-process call (no span) from an FFI/native hop;
   - list controller and DAO methods in `OTEL_INSTRUMENTATION_METHODS_INCLUDE`
     so plain function calls show up in the base.
2. **A full task end to end** on a real agent, then `audit-agent-trace`
   before any score is quoted. **Only one combination has ever finished a
   run here: `opencode` 1.19.5, answered by
   `opencode-go/deepseek-v4.1-flash`.** Nothing else is proven — not
   another OpenCode model, not another agent.
3. **Stacks for the other samples.** `online-study-system` and `openclinica`
   have cases but no scoring stack, so neither can be scored yet. Each needs
   `compose.yaml`, `Containerfile`, `.env` and the OpenTelemetry agent.
4. **Prove the other agents.** `src/bench/agents.py` registers `opencode`,
   `codex`, `claude` and `gemini`, and `--agent` selects one, but only
   `opencode` has run. Each of the others needs: a version whose own
   catalogue knows the wire name (`AGENT_MODEL`), its session directory
   confirmed against `agents.state()`, and a first run read before any
   score from it is quoted. What differs is the wire name, the bridge
   prefix and where the CLI writes its record.

## Parked

- **One phase instead of two.** Scoring no longer needs an Inspect sandbox, so
  solve and score could run in a single task. Kept apart for now because a kept
  tree can be re-graded without paying for the agent again.
- **App as native processes** (no Docker for scoring). Only worth it if the
  bench itself must run inside a container; costs the pinned toolchain.
- **Maven cache mount** (`--mount=type=cache`): a `pom.xml` change re-pays a
  long, silent download.
- **Re-prove gate sensitivity** on the host-driven scorer with the
  `broken-vote` tree.
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
- **`.agents/skills/` still describe the old Makefile CLI** and need the same
  pass the specs just had.

## Done

- Inspect-based bench; `main.py` is the whole command line.
- Samples under `src/samples/<slug>/{cases,env}`.
- Work orders with no docker, compose or container vocabulary.
- Scoring driven from the host: one compose project per case.
- OpenTelemetry in the mamute stack.
- `network_isolation` retired: with one scoring service there is no network
  contract left to grade.
- Solve is agent-agnostic: `AGENT`/`AGENT_MODEL`/`AGENT_VERSION` and
  `--agent`, one registry entry per CLI agent. Only `opencode` is verified
  (see Next 2 and 4).
- `templates/` deleted: the stack lives in `src/samples/<slug>/env/`, so
  there is no compose to copy into a pin — and a pin that carries one is
  refused at the first solve.
