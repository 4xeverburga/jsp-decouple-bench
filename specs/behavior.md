# SPEC — `behavior.md` (verbs, lifecycle, scorers)

Three verbs, all through `main.py`:

```bash
uv run python main.py manifests                              # list them
uv run python main.py task  --manifest <id> --model <p/m>    # solve, then score
uv run python main.py score --manifest <id> --run <run_id>   # score a kept tree
```

`main.py` is also the file Inspect loads (`inspect eval main.py@<task type>`),
so the same work can be driven by hand with two `inspect eval` calls.

Run environment (all required, no defaults): `BENCH_CHECKOUT` (the tree under
test), `BENCH_BASE_URL`, `APP_HTTP_PORT` and the sample's own public-URL
variable (`MAMUTE_PUBLIC_URL` for mamute). Credentials come from the sample's
`env/.env`, which `score` exports.

## The unit of work

A **manifest** (`seeds/manifests.json`) names one source, one task type, the
cases it is graded on, and the scorers assigned to it. A **sample** is one
`(source, case)` pair, id `slug@commit:case`; scoring gives every sample its
own stack because the goldens were captured on a pristine database.

Task types differ only in their work order: `decouple_slice` names one feature
boundary, `oneshot_decoupling` the whole app. Scorer ids are independent of
task type.

## 1. Solve

1. Cut a workspace from the pinned commit with the stack's container files
   removed (`solves.materialise`), as a one-commit git repo.
2. Inspect boots the **solve sandbox** from `env/solve.yaml`: the sample's
   toolchain, the workspace writable, and the database as a sidecar.
3. OpenCode runs inside it with `work_order(manifest)` as its prompt.
4. On cleanup, `solves.capture` writes `out/solves/<run_id>/`: `record.json`,
   `diff.patch` (new files included) and `tree/`.

The agent never has the docker socket, this repository or the supervisor's
home. A non-zero agent exit is recorded, not raised.

## 2. Score

Scoring has **no Inspect sandbox**. For each case the scorer, on the host:

1. starts a fresh compose project from `env/compose.yaml`, built from
   `BENCH_CHECKOUT`, and waits until every service is healthy or a one-shot
   exited 0 (`stack.running`);
2. snapshots the case's tables, plays `flow.py` with Playwright, snapshots
   again;
3. compares and scores;
4. removes the project (`down -v`), even on failure.

Samples run one at a time (`--max-samples 1`): they share the published port.
`stack.py` streams `docker compose` output as `[stack]` lines, because a first
build is minutes long and silent otherwise.

## 3. Scorers

A scorer never averages. `all_must_pass` reduces across a manifest's samples:
**the manifest passes only if every case passes.** A scorer that returns
`error` did not measure and is never averaged with a pass.

### `functional_parity`

Per case:

1. `before` = snapshot of the case's tables;
2. play the flow through Chromium, getting its artifacts dict;
3. `after` = snapshot; per table compute `inserted/updated/deleted` with the
   case's `key_columns` and `ignore_columns`;
4. compare the delta with `expect.json.db`, order-insensitively;
5. compare each artifact with `expect.json.artifacts` after normalization;
6. on any difference, keep the screenshot under `out/evidence/<slug>/`.

The shot is always staged and only promoted on failure: the failure can be
DB-only, with the page looking right, so the flow cannot know in advance.

Sensitivity is part of the contract: removing the `votes.save(...)` call from
the vote controller must fail both vote cases on the `Vote` family of tables.

### `trace_similarity` — **not built**

Intent: compare the spans a case produces with a base captured from the
pristine app, to tell whether calls inside the application are REST, FFI or
plain function calls. The stack already emits the spans (see
`src/samples/<slug>/env/otel-collector.yaml`); the scorer and the base are on
`ROADMAP.md`. It must never fabricate a score: without a base it is
`pending`, not a pass.

`network_isolation` and `topology` are retired. The scoring stack is a single
`front` service with no network contract to grade.

## 4. Isolation — the agent must not know

| never given to the agent | why |
|---|---|
| this repository (`seeds/`, `specs/`, `src/`, `out/`) | prompts, scorers and corpus |
| routes, case names (the manifest's `scope`) | the answer key's index |
| `expect.json`, `images/` | the answer key itself |
| docker, compose, a container runtime | would say where it is running |

The work order is a task type's contract plus the manifest's ask, and nothing
else. It uses no "benchmark", "golden", "case", "evaluation", "sandbox",
"container", "docker" or "compose". The toolchain is simply "already
installed here".

## 5. Determinism

- `en-US`, `UTC`, `1280x800`, a fresh database per sample;
- credentials from the sample's `.env`, never a prompt, case or flow;
- nothing depends on wall-clock time or host locale;
- ports and the clock are per run, so anything absolute in a golden is a bug.

## 6. Before a score is quoted

- on a no-op run `functional_parity` must be green; if it is red the source or
  the environment is wrong;
- read the agent's trace for anything that left its checkout
  (`audit-agent-trace`): a run that found the goldens is a leak, not a score.
