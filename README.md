# JSP-Decouple-Bench

A falsifiable benchmark for decoupling a legacy server-rendered app: an agent
gets a checkout and a work order, and its result is graded on **behaviour** —
browser artifacts and database rows — never on how the code looks.

Built on [Inspect](https://inspect.aisi.org.uk/), which owns the sandbox, the
run lifecycle and the logs.

## Vocabulary

| term | meaning |
|---|---|
| **source** | the code: project, branch, pinned commit — `seeds/sources.json` |
| **manifest** | cases over one source, plus the work order — `seeds/manifests.json` |
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

Then one command:

```bash
make eval MANIFEST=3 AGENT='opencode run --auto --model opencode-go/deepseek-v4.1-flash#high "$(cat)"'
```

It solves, scores, and both halves share one run id. Separately — solving is
expensive, scoring is cheap, so a tree can be graded again for free:

```bash
make solve   MANIFEST=3 AGENT='...'   # prints the run id, keeps the tree
make score   RUN=<id> MANIFEST=3      # boots the stack from that tree, grades it
make topology MANIFEST=3              # the shape gate: seconds, no stack
make view                             # browse the logs
```

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

## The two gates

- **functional_parity** — boots the stack, plays each case, compares browser
  artifacts *and* database deltas. Passes only if every case passes; an
  average would give half marks to a submission that decoupled nothing.
- **network_isolation** — reads the declared topology against the pinned one,
  no container, milliseconds. It must **fail** on an untouched tree: the
  pristine app reads the database directly.

Healthy is parity green with isolation red.

## Layout

```
inspect_bench.py          the tasks — the only file Inspect loads
src/bench/
  seeds.py                sources, manifests, the work order
  samples.py              (source, case) pairs
  compose.py              the stack's declared shape, pinned vs submitted
  cases.py                play a flow, read a golden
  db.py                   table snapshots through sandbox("db")
  delta.py, tabular.py    the delta algorithm and TSV parsing, copied verbatim
  artifacts.py            the normalizer (base URL, clocks, inline styles)
  scorers/                parity, topology, and the all-must-pass metric
  solves.py               a run id, its tree and its diff
  compose.*.yaml          sandbox per verb: solve, build, prebuilt
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

