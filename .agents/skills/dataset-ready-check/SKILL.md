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

Run this against ONE sample (`slug` from `seeds/samples.json`). Every check
must pass; a sample that fails any check is not publishable, because every
agent score produced on it would be meaningless. Write the result to
`out/ready/<sample>.md` (`out/` is gitignored).

**Prerequisites:** `prepare-repo-for-dataset` is done (history protected,
runnable, no origin pointer, OTel agent installed in the bench's
`Containerfile`), the sample has a stack in `src/samples/<slug>/env/`, and
the cases were authored with `add-bench-case`.

**What the commands are now.** The bench is `main.py` (verbs `task`,
`score`, `capture`, `manifests`) driven with `uv run`, and `specs/` is the
source of truth. There is no Makefile, no `bench.db`, no
`network_isolation` gate and no `topology` scorer — `functional_parity` is
the only gate, `trace_similarity` is not built yet (`ROADMAP.md`).

## Commands under test

```bash
cd jsp-decouple-bench

# 1. the stack builds and the app boots from the pin, then a golden is frozen
BENCH_CHECKOUT=$PWD/../<sample> uv run python main.py capture --manifest <n>

# 2. an untouched tree replays green (see §3 for the tree + run id)
BENCH_CHECKOUT=$PWD/out/solves/<run>/tree \
  uv run python main.py score --manifest <n> --run <run>

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
- The solve toolbox answers the toolchain under a **login** shell as well
  as a plain one, because the agent's commands may arrive either way
  (`prepare-repo-for-dataset` §2). `java` missing here while `mvn` works
  is the failure this catches:
  ```bash
  docker run --rm bench-solve-<slug>:local bash -lc \
    'for t in java javac mvn node; do
       printf "%-6s %s\n" "$t" "$(command -v $t || echo MISSING)"; done'
  ```
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
uv run python - <<'PY'
from pathlib import Path
from src.bench import solves
from src.bench.seeds import pin

slug, run = "mamute", "noop-mamute"
workspace = solves.materialise(run, Path("../mamute").resolve(), pin(slug))
solves.capture(run, workspace, {
    "agent": "none", "agent_model": "none", "agent_version": "none",
    "model": "noop", "note": "no-op self-check at the pinned tree",
})
print(solves.location(run) / "tree")
PY

BENCH_CHECKOUT=$PWD/out/solves/noop-mamute/tree \
  uv run python main.py score --manifest <n> --run noop-mamute
```
`materialise` cuts the tree; `capture` writes `tree/`, `diff.patch` and
`record.json` together — do not hand-roll the copy. `score` reads all
three (the record is what labels the score), and a hand-built tree with a
missing `record.json` fails on `solves.read` rather than scoring.

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
- The prompt (`seeds/prompts/manifests/<name>.md` + `seeds/prompts/task_types/<task_type>.md`) names
  no route, no case, no golden, and no `docker`/`compose`/`container`/
  `sandbox` word — the toolchain is "already installed here".
- **The solve sandbox itself.** A pristine tree and a clean prompt still
  leak if the *mount* is wrong, so check it from inside a running sandbox
  before spending a run:
  ```bash
  docker exec <workspace container> /bin/sh -c \
    'pwd; ls /workspace | head -3; ls /home 2>&1; env | grep BENCH_'
  ```
  `pwd` must be `/workspace`, `/workspace` must hold the tree, the
  supervisor's home must not exist there, and no `BENCH_*` variable may be
  visible. A run whose `pwd` is
  `.../jsp-decouple-bench/out/workspaces/<run>` has mounted the checkout at
  its host path, which names this repository to the agent — that happened,
  and the tree and the prompt were both clean while it did.
- After a real run, `audit-agent-trace` finds no read outside the
  checkout before any score is quoted.

## 7. At least one controller is fully covered

The intended record is `scope.covers` on the manifest entry — `controller`,
`handlers` (handler → case) and `not_driven` (handler → why it cannot be
reached) — written by `add-bench-case` §8. **No manifest populates it yet**:
every `scope` in `seeds/manifests.json` is `{cases, routes}` only.

```bash
grep -n 'covers' seeds/manifests.json    # empty = nothing recorded yet
```

While that is true, the check is an argument you make by reading the code,
not a field you open:

1. Open the target controller and list its handlers and the route each one
   registers (its annotations and `routes.properties`).
2. Walk the slice's `flow.py` and point at the step that reaches each
   handler.
3. A handler with no step is either `not_driven` — write down why it cannot
   be reached here — or a gap in the slice.

The routing must be the app's, not the manifest author's belief:
spot-check two handlers against `routes.properties` and the annotations.
Record the handler map in `out/ready/<slug>.md`; populating
`scope.covers` for the existing manifests is outstanding work
(`ROADMAP.md`), and this section tightens to "read the field" once it is
there.

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
