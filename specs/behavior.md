# SPEC — `behavior.md` (verbs, lifecycle, scorers)

Three verbs, all through `main.py`:

```bash
uv run python main.py manifests            # list them
uv run python main.py task  --manifest <id> --profile <solve>  # solve only
uv run python main.py score --manifest <id> --run <run_id> \
    --score-profile <judge>               # score a kept tree, any time
uv run python main.py capture --manifest <id> [--case <case>]  # freeze bases
```

`main.py` is also the file Inspect loads (`inspect eval main.py@<task type>`),
so the same work can be driven by hand with two `inspect eval` calls.

Parameters (all required, no defaults) come from `bench.env` at the repository
root, which `settings.py` reads and nothing else does: the browser, the
viewport, the locale, the clock, the timeouts and the model names. Copy
`bench.env.example` to `bench.env` once per checkout.

Run inputs come from the process environment, because they change per
invocation: `BENCH_CHECKOUT` (the tree under test) and `BENCH_SAMPLE_ENV`
(the sample's `env/`). The address a stack publishes is not one of them:
every stack picks a free host port, sets it as that stack's own
`APP_HTTP_PORT`, and plays its case against the sample's `target_url` in
`seeds/samples.json` with that port (`Stack.base_url`) — one value, so the
URL a case is played against cannot drift from the port compose binds,
and the sample's public-URL variable (`MAMUTE_PUBLIC_URL`) defaults to it.
The port `target_url` names is not used. Credentials come from the
sample's `env/.env`, which `score` exports.

### By hand, with `inspect eval`

The driver is convenience, not a requirement: both phases are ordinary
Inspect tasks and `main.py` is the file that defines them. What it carries
between the two runs is a run id and the tree that id names, so a hand-run
pair has to pass the same `manifest_id` and `run` — four `-T` values each,
no defaults — or the log stops describing what happened. `profile` is the
profile of the phase that runs: a solve profile in a solve, a score profile
in a score.

**Score** is standalone. It starts the stack itself and reads only the tree:

```bash
export BENCH_CHECKOUT=$PWD/out/solves/<run_id>/tree
set -a; . src/samples/mamute/env/.env; set +a   # the sample's credentials
uv run inspect eval main.py@decouple_slice \
  -T manifest_id=3 -T phase=score -T run=<run_id> \
  -T profile=judge-claude-opus-5.5-high \
  --model mockllm/model --max-samples 4 --metadata attempt=$(uuidgen)
```

Export the judge's credential too (`ANTHROPIC_API_KEY` for that profile).
The solve profile is not passed: the task reads it from the run's record
and labels the log with it; `--model` is the model Inspect demands, and `BENCH_SCORE_MODEL` is
what the driver passes there. `--max-samples` is how many cases replay at
once (the driver passes `SCORE_MAX_SAMPLES`); each has its own stack and
port, and `STACK_MAX_LIVE` caps the stacks on the host whatever it says.
`attempt` is how the driver finds this invocation's log; by hand it is
only a label.

**Solve** needs what the driver would have prepared:

1. a workspace cut from the pin — `solves.materialise`, which also refuses a
   pin that carries a stack file;
2. `BENCH_SAMPLE_ENV`, the sample's `env/`, for the sandbox's `solve.yaml`;
3. `SOLVE_ROOT`, and the profile's credentials (`settings.credentials`).

```bash
export RUN=$(uv run python -c 'import uuid; print(uuid.uuid4().hex)')
export BENCH_CHECKOUT=$(uv run python -c "from pathlib import Path; import settings; \
from src.bench import solves; from src.bench.seeds import pin; \
print(solves.materialise(Path(settings.checkout()), pin('mamute')))")
export BENCH_SAMPLE_ENV=$PWD/src/samples/mamute/env SOLVE_ROOT=/workspace
set -a; . bench.env; set +a                          # the profile's keys
uv run inspect eval main.py@decouple_slice \
  -T manifest_id=3 -T phase=solve -T run=$RUN \
  -T profile=opencode-v1-deepseek-flash-medium \
  --model openai-api/opencode-go/deepseek-v4.1-flash
```

A solve keeps its own tree under `out/solves/<run_id>/` — the task's cleanup
hook writes it, not the driver — so the score command above can follow it
with nothing in between. Run side by side, this is also the only place a
stale `BENCH_CHECKOUT` shows: the score phase trusts it.

## The unit of work

A **manifest** (`seeds/manifests.json`) names one source, one task type, the
cases it is graded on, and the scorers assigned to it. A **sample** is one
`(source, case)` pair, id `slug@commit:case`; scoring gives every sample its
own stack because the goldens were captured on a pristine database.

Task types differ only in their work order: `decouple_slice` names one feature
boundary, `oneshot_decoupling` the whole app. Scorer ids are independent of
task type.

## 1. Solve

1. Cut a workspace from the pinned commit (`solves.materialise`), as a
   one-commit git repo. The pin must carry no stack file: the stack is the
   bench's, and a pin that still has one is refused, not scrubbed.
2. Inspect boots the **solve sandbox** from `env/solve.yaml`: the sample's
   toolchain, the workspace writable, and the database as a sidecar.
3. The agent runs inside it with `work_order(manifest)` as its prompt:
   the profile's `agent`, one entry of `src/agents/`, with the answerer model
   passed directly to native `react` or bridged to a CLI agent.
4. On cleanup, `solves.capture` writes `out/solves/<run_id>/`: `record.json`,
   `diff.patch` (new files included) and `tree/`.

The agent never has the docker socket, this repository or the supervisor's
home. A non-zero agent exit is recorded, not raised.

## 2. Score

Scoring has **no Inspect sandbox**. For each case the score phase's solver,
`replay.replayed_case`, on the host:

1. starts a fresh compose project from `env/compose.yaml`, built from
   `BENCH_CHECKOUT`, and waits until every service is healthy or a one-shot
   exited 0 (`stack.running`);
2. snapshots the case's tables, plays `flow.py` with Playwright, snapshots
   again;
3. copies the collector's span file out to `out/traces/<slug>/`, waiting
   out its export batch, because `down -v` deletes the volume;
4. removes the project (`down -v`), even on failure;
5. leaves the observation — the flow's failure or artifacts, the table
   deltas, the trace path — in the sample's store (`state.store["replay"]`).

Then every scorer the manifest names judges that one run: the flow is
played once, so two gates never grade two different runs of the app. A
missing trace leaves parity's verdict alone and makes `trace_similarity`
an error.

Samples run side by side (`--max-samples SCORE_MAX_SAMPLES`): every stack is
its own compose project on a free host port it picks itself, retried when
another process takes it first, and `STACK_MAX_LIVE` slots (`flock`s under
`out/locks/`) cap the stacks up on the host across every bench process. A
case that finds no free slot waits for one, inside the score budget.
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

### `trace_similarity`

Per case, on the spans the replay kept:

1. condense them (`spans.condense`): the browser's requests in order, each
   with what served it — `SQL <op> <table>`, the app's own `HTTP CLIENT`
   calls and, nested under one, the `SERVER` span that answered it. Ids,
   timestamps, hosts, numbers and slugs are erased; Hibernate wrappers and
   the JDBC driver's connection chatter are dropped; static assets are not
   requests; identical siblings fold into `xN`;
2. **floor**: no `HTTP CLIENT` call answered by the app's own `SERVER` span
   means no boundary — `INCORRECT`, with no model asked. A no-op tree ends
   here;
3. **judge**: the score profile's model reads the work order (the sample's
   input), the case's `trace.json` (BEFORE) and the condensed tree (AFTER),
   and answers four booleans in a fixed schema — `browser_contract_kept`,
   `boundary_crossed`, `page_side_clean`, `writes_preserved` — plus the
   requests it put in scope and an explanation. The verdict is their
   conjunction, computed by the scorer.

No spans, no `trace.json`, or no parseable verdict raises: the case was
not measured. The judge's prompt is `scorers/trace_similarity/judge.md`; it
is the bench's and never reaches the agent.

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
