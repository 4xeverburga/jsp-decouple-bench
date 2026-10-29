# JSP-Decouple-Bench

A falsifiable benchmark for decoupling a legacy server-rendered app: an agent
gets a checkout and a work order, and its result is graded on **behaviour** —
browser artifacts and database rows — never on how the code looks.

Built on [Inspect](https://inspect.aisi.org.uk/), which owns the sandbox, the
run lifecycle and the logs.

## Vocabulary

| term | meaning |
|---|---|
| **source** | code, pin, and runtime stack config — `seeds/sources.json` |
| **manifest** | one logical task: source, work order, cases, and assigned scorers — `seeds/manifests.json` |
| **sample** | one (source, case) pair; Inspect gives each its own stack |
| **case** | one graded behaviour: a flow plus its frozen `expect.json` |

A manifest is addressed by its **id**; `python main.py manifests` lists them all.

## Run it

Export the run environment once per shell:

```bash
export BENCH_CHECKOUT=/abs/checkout
export BENCH_BASE_URL=http://localhost:8080
export APP_HTTP_PORT=8080 MAMUTE_PUBLIC_URL=$BENCH_BASE_URL
```

Run the manifest task. The agent runs first; every assigned scorer runs
automatically afterward against the saved tree, with one run ID for both:

```bash
uv run python main.py task --manifest 3 --model anthropic/claude-sonnet-4-5
```

`main.py` is also the file Inspect loads (`inspect eval main.py@<task type>`),
so `python main.py` is the whole command line:

| verb | what it does |
|---|---|
| `task` | solve and score one manifest, on one run id |
| `score` | only grade a tree a solve already kept (`--run <id>`) |
| `manifests` | list the manifests, their task type and their cases |

Nothing here is built, so there is no build system to drive it. Two
`inspect eval` calls do the work; the driver holds only what they cannot
hand each other — a run id, and the checkout derived from it. Logs are
Inspect's own (`uv run inspect view --log-dir out/evals`), and linting is
`uv run ruff check main.py src`.

### The same run, by hand

The exports above still apply; nothing else about the driver is required —
it is two `inspect eval` calls. Pick any run id (the manifest's **task type**
is the `@task` name, and `manifests` prints it):

```bash
RUN=$(python3 -c 'import uuid;print(uuid.uuid4().hex)')

# solve: the agent, in the workspace built for it
uv run inspect eval main.py@decouple_slice \
  -T manifest_id=3 -T phase=solve -T run=$RUN \
  --model anthropic/claude-sonnet-4-5 --display plain --log-dir out/evals

# score: the tree it left; the scorer starts the sample's stack itself
BENCH_CHECKOUT=$PWD/out/solves/$RUN/tree \
uv run inspect eval main.py@decouple_slice \
  -T manifest_id=3 -T phase=score --max-samples 1 \
  --model mockllm/model --display plain --log-dir out/evals
```

Three things to keep straight, all of which the driver does for you: `$RUN`
must be the same in both commands; `BENCH_CHECKOUT` must be *that* run's
tree — Inspect does not check, so a stale path grades the previous tree in
silence.

## The agent

**A command, in the sandbox** — this is what exists. `AGENT` is a shell
command; it runs inside the container Inspect provisioned, with the prompt on
stdin, and it sees the checkout and nothing else: no docker socket, no home
directory. It brings its own credentials.

**A model through Inspect** — not built. `--model provider/model` plus
`OPENAI_API_KEY` (or another provider's), with a solver that hands the model
the same tools, would measure a model instead of an agent product. Those are
different numbers and should never share a label. Until then
`--model mockllm/model` is only there to satisfy the interface.

## Scorers

- Each manifest lists its scorer IDs. The score task runs every assigned
  scorer automatically after solving.
- Scoring uses the selected source's Compose file. The scorer starts that
  stack itself with `docker compose` from the host (`src/bench/stack.py`),
  one per case, and removes it afterwards; Playwright and the database reads
  run on the host too. There is no Inspect sandbox in the score phase, so
  nothing runs Docker inside Docker.
- **functional_parity** — boots the stack, plays each case, compares browser
  artifacts (including normalized DOM) *and* database deltas. It passes only
  if every case passes.
- **trace_similarity** — not built yet. Every sample's stack already emits
  OpenTelemetry traces (see the sample's `env/otel-collector.yaml`); the
  scorer will compare their shape with the pristine app's, which is how a
  REST call, an FFI call and a plain function call tell apart.

Only `decouple_slice` and `oneshot_decoupling` are task types; scorer IDs are
independent of task type.

## Layout

```
main.py                   the tasks, and the command line — Inspect loads this
src/bench/
  cli.py                  task, score, manifests — the run id they share
  seeds.py                sources, manifests, the work order
  samples.py              (source, case) pairs
  compose.py              the scoring stack and the solve workspace, per sample
  stack.py                starts and removes a case's stack from the host
  solves.py               a run id, its tree and its diff
  settings.py             paths and the environment, read when asked
  scorers/
    functional_parity/    the gate, and what grades a case
      parity.py           the scorer: artifacts and rows, compared
      cases.py            play a flow, read a golden
      db.py               table snapshots through the case's stack
      delta.py            the delta algorithm, copied verbatim
      tabular.py          TSV parsing shared by every SQL adapter
      artifacts.py        the normalizer (base URL, clocks, inline styles)
    metrics.py            all_must_pass
src/samples/<sample>/
  env/                    compose.yaml, Containerfile, .env, solve.yaml,
                          otel-collector.yaml (where the stack emits traces)
  cases/                  the graded flows and their goldens
```

`delta.py` is copied rather than reimplemented on purpose: the goldens were
produced by it, so rewriting it would quietly change what "matches" means.
A case lives in `src/samples/<sample>/cases/`; the scorer only plays it.

## Not done yet

- The docs in `specs/` and `.agents/skills/` are from the previous
  implementation and still describe a CLI that no longer exists.

## What a run costs

The first build of a sample downloads its whole dependency set into an empty
`~/.m2` — for mamute that is about seven minutes, because the Dockerfile runs
Maven quiet and the layer is not cached until it completes once. After that
the layer is reused and a two-case score is about ninety seconds. There is no
`--mount=type=cache` on `/root/.m2`, so a change to `pom.xml` pays the
download again.

`--display log` keeps step output in the log; without it Inspect draws a TUI
and a redirected run looks frozen.

