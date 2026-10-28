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

A manifest is addressed by its **id**; `make manifests` lists them all.

## Run it

Export the run environment once per shell:

```bash
export BENCH_CHECKOUT=/abs/checkout
export BENCH_BASE_URL=http://localhost:8080
export APP_HTTP_PORT=8080 MAMUTE_PUBLIC_URL=$BENCH_BASE_URL
export BENCH_AGENT_IMAGE=<image the agent runs in>
set -a; . "$BENCH_CHECKOUT/.env"; set +a
```

Run the manifest task. The agent runs first; every assigned scorer runs
automatically afterward against the saved tree, with one run ID for both:

```bash
make task MANIFEST=3 AGENT='opencode run --auto --model opencode-go/deepseek-v4.1-flash#high "$(cat)"'
```

`make view` browses the Inspect logs; `make manifests` lists the available
logical tasks.

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
- Scoring uses the selected source's Compose file and default service. The
  adapter adds Inspect metadata in a temporary sidecar; it does not keep a
  global app-specific stack file.
- **functional_parity** — boots the stack, plays each case, compares browser
  artifacts (including normalized DOM) *and* database deltas. It passes only
  if every case passes.
- **network_isolation** — compares the submitted topology with the pinned
  contract. The whole-app manifest assigns it; it must fail on an untouched
  tree because the pristine app reads the database directly.

Only `decouple_slice` and `oneshot_decoupling` are task types; scorer IDs are
independent of task type.

## Layout

```
inspect_bench.py          the tasks — the only file Inspect loads
src/bench/
  seeds.py                sources, manifests, the work order
  samples.py              (source, case) pairs
  compose.py              source Compose setup and topology comparison
  cases.py                play a flow, read a golden
  db.py                   table snapshots through sandbox("db")
  delta.py, tabular.py    the delta algorithm and TSV parsing, copied verbatim
  artifacts.py            the normalizer (base URL, clocks, inline styles)
  scorers/                parity, topology, and the all-must-pass metric
  solves.py               a run id, its tree and its diff
  compose.solve.yaml      isolated agent workspace
  corpus/<source>/<case>/ flow.py + expect.json
```

`delta.py` is copied rather than reimplemented on purpose: the goldens were
produced by it, so rewriting it would quietly change what "matches" means.

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

