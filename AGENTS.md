# AGENTS — the supervisor's contract

This repository runs a benchmark. The agent under evaluation never sees it and
never learns it is being measured. If you were handed a checkout and a prompt,
this file is not for you.

## What owns what

| thing | where |
|---|---|
| the code under test, its pin and stack entrypoint | `seeds/sources.json` |
| the graded cases and the work order | `seeds/manifests.json` |
| the answer key: flows and goldens | `src/samples/<sample>/cases/` |
| the stack, Containerfile, .env, OpenTelemetry collector | `src/samples/<sample>/env/` |
| starting and removing a case's stack | `src/bench/stack.py` |
| the verdicts | `src/bench/scorers/` |
| direction, and what is parked | `ROADMAP.md` |

Inspect owns the agent's sandbox, the run lifecycle and the logs. Scoring has
no sandbox: the scorer starts each case's stack itself, from the host. The
bench keeps only what no framework can supply: the work order, the case
corpus, the delta algorithm, and the shape rules. `specs/` describes the
modules and the lifecycle.

## Hard rules

1. **Never expose this repository to the agent.** Not the seeds, not the
   corpus, not the logs. It gets a checkout and a prompt.
2. **A prompt is a work order, not an exam.** No "benchmark", "golden",
   "case", "evaluation", no list of graded routes, and no word that says where
   it runs: "docker", "compose", "container", "sandbox". The toolchain is
   "already installed here". The agent reads exactly `work_order(manifest)`:
   a task type's contract plus the manifest's ask.
3. **Never leak scope.** Routes, case names and goldens are what the agent is
   judged on, never what it is given.
4. **One sample, one stack.** Every case gets its own stack, started by the
   scorer and removed after it, because the goldens were captured on a
   pristine database. This is why samples are (source, case) pairs and not
   just code.
5. **Determinism.** `en-US`, `UTC`, `1280x800`, a fresh database per sample.
   No time-, locale- or host-dependent behaviour anywhere.
6. **Credentials come from the source's `.env`**, never from a prompt, a case
   or a flow.
7. **The bench owns the stack.** Compose, Containerfile, `.env` and the
   OpenTelemetry setup live in `src/samples/<sample>/env/`, never in the tree
   the agent gets.
8. **A gate never averages.** `all_must_pass` reduces across samples; a run
   passes only if every case passes.
9. **PEP 8, 79 columns**, enforced by `ruff` through `uv run`. Dependencies
   live in `pyproject.toml` and `uv.lock`, nowhere else.

## Running one

```bash
export BENCH_CHECKOUT=/abs/checkout BENCH_BASE_URL=http://localhost:8080
export APP_HTTP_PORT=8080 MAMUTE_PUBLIC_URL=$BENCH_BASE_URL

uv run python main.py task --manifest 3 --model anthropic/claude-sonnet-4-5
```

The solve runs OpenCode in its own workspace, then every scorer assigned to
the manifest grades the tree it left. `out/solves/<run id>/` keeps the tree,
the diff and a record of what ran. `python main.py score --manifest N --run ID`
grades a kept tree again without paying for the agent.

There is no Makefile and nothing is built: `main.py` is the whole command
line (`task`, `score`, `manifests`) and also the file Inspect loads
(`inspect eval main.py@<task type>`). Scoring prints its progress as
`[stack]` lines; a first build of a sample is minutes long.

## Traces

Every stack runs the app under the OpenTelemetry Java agent, configured only
through `OTEL_*` in the sample's `.env`; a collector writes the spans to
`/traces/traces.jsonl`. Read them while the stack is up, with
`docker compose cp collector:/traces/traces.jsonl <dest>`; they flush a few
seconds after a request. The `trace_similarity` scorer that compares them is
not built yet (`ROADMAP.md`).

In a Containerfile, add new layers **last**: one above the Maven layer
invalidates its cache and costs a long, silent download.

## Before a score is quoted

- On a no-op run parity must be green. If it is red, the source or the
   environment is wrong and no score on it means anything.
- read the trace: what the agent actually read, and whether any path left its
  checkout. A run that found the goldens is not a score, it is a leak.
- a scorer that returns `error` did not measure. Never average it with a pass.
