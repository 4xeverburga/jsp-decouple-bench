# AGENTS — contract for an agent evaluated on this benchmark

## What you receive

- A sample checkout, **already at the pinned commit** (`SAMPLE.commit_sha`),
  and the filesystem path to it.
- A manifest prompt (`TASK_MANIFEST.prompt`) naming the feature boundary.
- The case scope: the case names your work is graded against.

You work **inside the sample checkout**. The bench repo (this one) is not
your worktree: `bench.db`, `src/gates/functional_parity/cases/`, `seeds/`
and `specs/` are the grader.

## What you must do

Decouple the named boundary: RESTify the controllers that serve its routes,
remove the server-rendered JSP/tag rendering for that flow, keep behaviour
parity.

**There is no edit whitelist.** Shared tags, interceptors, config, other
pages — change whatever the decoupling needs. The boundary is a
*verification scope*, not an edit scope.

## Hard rules

1. **Work at the pinned commit.** The runner checks the worktree out to
   `SAMPLE.commit_sha` and aborts if it is dirty. Do not move the commit,
   do not rewrite history, do not `git reset --hard` over the sample's own
   work.
2. **Legacy unit tests are out of scope.** Decoupling legitimately breaks
   view-layer tests. Do not spend effort resurrecting them; the gates are
   the criteria.
3. **No network beyond the compose stack.** The environment is
   self-contained; external calls fail the run.
4. **Determinism.** The run uses `en-US`, `UTC`, `1280x800`. Do not
   introduce time-, locale- or host-dependent behaviour. Credentials come
   from the sample's `.env` — never hardcode them.
5. **Do not weaken the stack's declared shape.** `network_isolation` fails
   if the app joins `host` networking, adds networks, or publishes ports
   the sample's `compose.yaml` does not declare.

## How you are scored

```bash
make gate GATE_ID=functional_parity RUN_ID=<run_id>
make gate GATE_ID=network_isolation RUN_ID=<run_id>
```

Each gate writes `out/runs/<run_id>/gates/<gate_id>.json`:

```json
{
  "gate_id": "functional_parity",
  "gate_version": 1,
  "run_id": "3f2c…",
  "value": 1.0,
  "verdict": "pass",
  "threshold": 1.0,
  "direction": "maximize",
  "duration_s": 812.4,
  "details": [{"case": "vote-flow__upvote-increments-count", "verdict": "pass"}],
  "notes": []
}
```

- `verdict`: `pass | fail | error | pending` (exit codes 0 / 1 / 2 / 3).
- `value`: normalised to `[0,1]`, or `null` when the gate could not measure.
- **A gate never averages.** `pass` requires every sub-check to pass.

Passing a run means `functional_parity` **and** `network_isolation` are
`pass`. `trace_similarity` reports `pending` until its oracle is
implemented — it is not a pass criterion yet, and it will never be
hand-scored.

## Running the app yourself

```bash
cd <sample-location>
docker compose -p bench-debug -f compose.yaml up -d --wait
# app is on http://localhost:${BENCH_HTTP_PORT:-default}
docker compose -p bench-debug down -v
```

Always tear the stack down (`-v`): case expectations assume a freshly
reset database so ids are deterministic.
