# SPEC — `behavior.md` (verbs, lifecycle, scorers)

Three verbs, all through `main.py`:

```bash
uv run python main.py manifests                              # list them
uv run python main.py task  --manifest <id> --profile <name> # solve, then score
uv run python main.py score --manifest <id> --run <run_id>   # score a kept tree
```

`main.py` is also the file Inspect loads (`inspect eval main.py@<task type>`),
so the same work can be driven by hand with two `inspect eval` calls.

Parameters (all required, no defaults) come from `.env` at the repository
root, which `settings.py` reads and nothing else does: the browser, the
viewport, the locale, the clock, the timeouts and the model names. Copy
`.env.example` to `.env` once per checkout.

Run inputs come from the process environment, because they change per
invocation: `BENCH_CHECKOUT` (the tree under test) and `BENCH_SAMPLE_ENV`
(the sample's `env/`). The address a stack publishes is not one of them
any more: `BENCH_BASE_URL` and the `APP_HTTP_PORT` that serves it are
derived by the driver from the sample's `target_url` in
`seeds/samples.json` — one field, so the URL a case is played against
cannot drift from the port compose binds — and the sample's own
public-URL variable (`MAMUTE_PUBLIC_URL`) defaults to it. Credentials come
from the sample's `env/.env`, which `score` exports.

### By hand, with `inspect eval`

The driver is convenience, not a requirement: both phases are ordinary
Inspect tasks and `main.py` is the file that defines them. What it carries
between the two runs is a run id and the tree that id names, so a hand-run
pair has to pass the same `-T` values — seven of them, no defaults — or the
log stops describing what happened.

**Score** is standalone. It starts the stack itself and reads only the tree:

```bash
export BENCH_CHECKOUT=$PWD/out/solves/<run_id>/tree
export BENCH_BASE_URL=http://localhost:8090 APP_HTTP_PORT=8090   # the seed's target_url
set -a; . src/samples/mamute/env/.env; set +a   # the sample's credentials
uv run inspect eval main.py@decouple_slice \
  -T manifest_id=3 -T phase=score -T run=<run_id> \
  -T profile=opencode-deepseek-flash \
  --model mockllm/model --max-samples 1
```

`profile` is a label in this phase (the driver takes it from the run's
record); `--model` is the model Inspect demands, and `BENCH_SCORE_MODEL` is
what the driver passes there. One sample at a time: the cases share the
published port.

**Solve** needs what the driver would have prepared:

1. a workspace cut from the pin — `solves.materialise`, which also refuses a
   pin that carries a stack file;
2. `BENCH_SAMPLE_ENV`, the sample's `env/`, for the sandbox's `solve.yaml`;
3. `SOLVE_ROOT`, and the profile's credentials (`settings.credentials`).

```bash
export RUN=$(uv run python -c 'import uuid; print(uuid.uuid4().hex)')
uv run python -c "from pathlib import Path; import settings; \
from src.bench import solves; from src.bench.seeds import pin; \
solves.materialise('$RUN', Path(settings.checkout()), pin('mamute'))"
export BENCH_CHECKOUT=$PWD/out/workspaces/$RUN
export BENCH_SAMPLE_ENV=$PWD/src/samples/mamute/env SOLVE_ROOT=/workspace
set -a; . .env; set +a                          # the profile's keys
uv run inspect eval main.py@decouple_slice \
  -T manifest_id=3 -T phase=solve -T run=$RUN \
  -T profile=opencode-deepseek-flash \
  --model openai-api/opencode-go/deepseek-v4.1-flash
```

A solve keeps its own tree under `out/solves/<run_id>/` — the task's cleanup
hook writes it, not the driver — so the score command above can follow it
with nothing in between. Run side by side, this is also the only place a
stale `BENCH_CHECKOUT` shows: the score phase trusts it.

## Agents and answerers

Two independent choices, joined by the bridge, and named together by one
profile in `runs.yaml` (`--profile`):

| | profile keys | what it decides |
|---|---|---|
| **agent** | `agent`, `agent_model`, `agent_version` | which implementation and tool set solves the work order |
| **answerer** | `answer_model`, `model_env`, `reasoning_effort`, `model_args` | which model generates the tokens, and so what a score is attributed to |

The task builds the answering `Model` itself, so it is not Inspect's active
model and the eval's `--reasoning-effort` / `-M` would never reach it: the
profile's effort and args are set on that model directly.

The native `react` agent uses the answerer directly and has sandbox-backed
shell and text-editor tools. Its `agent_model` and `agent_version` values
are recorded labels; they do not select a second model or CLI version.
The CLI agents use `agents.aliases()` to map the name a CLI sends onto the
`Model` the eval built. Two constraints survive that:

- the **wire model** must exist in the CLI's own catalogue. The CLI checks it
  before sending anything, so a version that predates the slug refuses it and
  no alias can rescue it (opencode 1.14.42 vs `deepseek-v4.1-flash`);
- the **answerer's provider** must have its credentials named in the
  profile's `model_env` and set in `.env`. The agent needs none of its own: its
  CLI sandbox gets a dummy credential and the bridge answers. Native ReAct
  uses the answerer's configured credentials directly.

`model_env` is what keeps a new provider out of the code: it lists the
variable names the provider reads — one `*_API_KEY` for an Inspect provider,
`<SERVICE>_API_KEY` + `<SERVICE>_BASE_URL` for an OpenAI-compatible gateway,
nothing for `mockllm` — and `settings.credentials` forwards exactly those. Each
named variable is required; an empty list is a real answer, an absent one is
an error.

What is proven end to end: `opencode` 1.19.5 answered by
`opencode-go/deepseek-v4.1-flash`. `codex`, `claude` and `gemini` are
registered and selectable; the native `react` agent is implemented but
still needs a real slice run before its provider/tool compatibility is
considered proven.

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

Scoring has **no Inspect sandbox**. For each case the scorer, on the host:

1. starts a fresh compose project from `env/compose.yaml`, built from
   `BENCH_CHECKOUT`, and waits until every service is healthy or a one-shot
   exited 0 (`stack.running`);
2. snapshots the case's tables, plays `flow.py` with Playwright, snapshots
   again;
3. copies the collector's span file out to `out/traces/<slug>/`, waiting
   out its export batch, because `down -v` deletes the volume — best
   effort, so a missing trace never turns a verdict into an error;
4. compares and scores;
5. removes the project (`down -v`), even on failure.

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
