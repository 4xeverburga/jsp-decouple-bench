---
name: dataset-ready-check
description: >
  Validate that a sample is ready for release in this benchmark: it boots
  from a fresh clone at its pinned commit, an untouched tree reproduces the
  goldens, the cases are sensitive to real breakage, results are
  deterministic, the agent cannot see the answer key, at least one controller
  is fully covered, and the OpenTelemetry agent produces a usable trace base
  for `trace_similarity`. Use when asked to "check if this sample is dataset
  ready", "validate the sample", or "is this sample ready to publish".
---

# Dataset-ready check for a sample

Run this against ONE sample (`slug` from `seeds/sources.json`). Every check
must pass; a sample that fails any check is not publishable, because every
agent score produced on it would be meaningless. Write the result to
`out/ready/<sample>.md` (`out/` is gitignored).

**Prerequisites:** `prepare-repo-for-dataset` is done (history protected,
runnable, no origin pointer, OTel agent installed in the bench's
`Containerfile`), the sample has a stack in `src/samples/<slug>/env/`, and
the cases were authored with `test-slice`.

**What the commands are now.** The bench is `main.py` (verbs `task`,
`score`, `capture`, `manifests`) driven with `uv run`, and `specs/` is the
source of truth. There is no Makefile, no `bench.db`, no
`network_isolation` gate and no `topology` scorer — `functional_parity` is
the only gate, `trace_similarity` is not built yet (`ROADMAP.md`).

## Commands under test

```bash
cd jsp-decouple-bench

# 1. the stack builds and the app boots from the pin, then a golden is frozen
BENCH_CHECKOUT=$PWD/../<sample> BENCH_BASE_URL=http://localhost:<port> \
  APP_HTTP_PORT=<port> uv run python main.py capture --manifest <n>

# 2. an untouched tree replays green (see §3 for the tree + run id)
BENCH_CHECKOUT=$PWD/out/solves/<run>/tree BENCH_BASE_URL=http://localhost:<port> \
  APP_HTTP_PORT=<port> uv run python main.py score --manifest <n> --run <run>

# 3. a real agent, end to end (optional here; mandatory before quoting a score)
uv run python main.py task --manifest <n> --agent opencode
```

Scoring drives the stack from the host (`src/bench/stack.py`): one compose
project per case, started and removed by the scorer, `[stack]` progress on
stderr. A first build of a sample is minutes long.

## 1. It boots from the pin, on the bench's stack

- `src/samples/<slug>/env/` holds `compose.yaml`, `Containerfile`,
  `entrypoint.sh`, `.env`, `.env.example`, `otel-collector.yaml`,
  `solve.yaml` and `toolbox/`. Nothing of it is in the sample tree.
- The pin carries **no stack file**: `main.py capture` and the solve phase
  both cut the tree with `solves.materialise`, which raises and lists the
  offending paths if one is there.
- `capture` finished: the app answered, the seeded account logged in, the
  flow ran (a failed flow raises; there is no "captured anyway").
- `docker compose ps` after the run shows nothing left over, and no
  `bench-*` project or network survives (`down -v --remove-orphans`).

## 2. The golden is generated, and only here

- `expect.json` is git-clean after a capture, or its only change is a
  deliberate re-capture committed in the same change as the case.
- `case.json` declares every table the delta shows; a table that changes
  outside the spec means the contract is incomplete.

## 3. An untouched tree reproduces the goldens

The scored artifact is a kept tree, so the no-op check needs one. Cut the
pin, keep it as a run, keep its diff empty:

```bash
PORT=8090
uv run python - <<'PY'
import json, shutil
from pathlib import Path
from src.bench import solves
from src.bench.seeds import pin

slug, run = "mamute", "noop-mamute"
tree = solves.materialise(run, Path("../mamute").resolve(), pin(slug))
target = solves.location(run)
shutil.copytree(tree, target / "tree")
(target / "diff.patch").write_bytes(b"")
(target / "record.json").write_text(json.dumps({
    "agent": "none", "agent_model": "none", "agent_version": "none",
    "model": "noop", "run_id": run, "diff_bytes": 0,
}, indent=2) + "\n")
PY

BENCH_CHECKOUT=$PWD/out/solves/noop-mamute/tree \
BENCH_BASE_URL=http://localhost:$PORT APP_HTTP_PORT=$PORT \
  uv run python main.py score --manifest <n> --run noop-mamute
```

Every case must come back `correct`. If it is red, the pin or the stack is
wrong — no score taken on this sample means anything, and a real agent's
result would be indistinguishable from the bench's own breakage.

## 4. It is deterministic

Run the capture a second time and compare. `captured_at` is provenance and
the only field allowed to move:

```bash
git diff -U0 -- src/samples/<slug>/cases/<case>/expect.json \
  | grep '^[+-]' | grep -v captured_at     # must print nothing
```

Then run §3 twice: same verdicts, same differing tables. Ids are stable
because every fresh boot replays the same seed; a case that depends on
another case's rows will show up here.

## 5. The cases are sensitive to real breakage

Break the behaviour on a scratch copy — comment out the `save(...)` a
graded flow exercises — score it, and require `INCORRECT` with the
expected tables named and a screenshot under `out/evidence/<slug>/`.
Restore the copy afterwards (never the pin).

A case that stays green when the write is gone is asserting on the wrong
artifact, and the agent would pass it by accident.

## 6. The agent cannot see the answer key

Checked against the **tree**, not against intentions:

- `git grep -InE 'BENCH_|golden|expect\.json|the bench|graded|harness'`
  is empty apart from the app's own code.
- No origin pointer: `UPSTREAM.md` absent, no project URL in `README` /
  `AGENTS.md`, no "mirror of" sentence.
- The pin is one commit in the run's checkout (`git rev-list --count HEAD`
  is `1` once materialised) and has no refs or remotes.
- The prompt (the manifest `prompt` + the task type's `base_prompt`) names
  no route, no case, no golden, and no `docker`/`compose`/`container`/
  `sandbox` word — the toolchain is "already installed here".
- After a real run, `audit-agent-trace` finds no read outside the
  checkout before any score is quoted.

## 7. At least one controller is fully covered

`scope.covers.handlers` in `seeds/manifests.json` maps every handler of one
controller to the case that drives it, and `not_driven` explains the rest.
Read the controller and spot-check two entries: the routing must be the
app's, not the manifest author's belief.

## 8. The trace base exists (for the scorer that is not built yet)

- The scoring stack runs the app under the pinned OpenTelemetry Java agent
  and ships to its own `collector` service; the agent is attached only at
  run time (`CATALINA_OPTS` / `MAVEN_OPTS`), configured only through
  `OTEL_*` in the sample's `env/.env`.
- With the stack up, `docker compose cp collector:/traces/traces.jsonl
  <dest>` yields spans for a graded flow (HTTP server, JDBC, and the
  container's own client hops). Spans flush a few seconds after the
  request.
- The app boots and passes its healthcheck with the collector dead, and
  the cases stay green with the agent attached (`functional_parity` must
  not depend on tracing).
- `trace_similarity` is pending: this check proves the base can be taken,
  not that it is compared yet.

## 9. Verdict

Write `out/ready/<sample>.md`: each check, the command that proved it, and
`pass` / `fail` with the evidence path. A sample is ready only when every
check passes; a `trace`-dependent scorer stays `pending` on all samples
until it exists, and a `pending` is never averaged into a pass.
