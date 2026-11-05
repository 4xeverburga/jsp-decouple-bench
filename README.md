<p align="center">
  <a href="https://chiffonstack.kekeros.com">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="assets/chiffonstack-isotype.svg">
      <img src="assets/chiffonstack-isotype-negative.svg" alt="ChiffonStack" width="72">
    </picture>
  </a>
</p>

<h1 align="center">jsp-decouple-bench</h1>

<p align="center">
  Can a coding agent put a REST boundary inside a legacy JSP app<br>
  without the browser, the database or the rest of the app noticing?
</p>

<p align="center">
  <img alt="python" src="https://img.shields.io/badge/python-3.13-3776ab">
  <img alt="inspect-ai" src="https://img.shields.io/badge/inspect--ai-0.3.286-ff8e05">
  <img alt="playwright" src="https://img.shields.io/badge/playwright-1.63-2ead33">
  <img alt="opentelemetry" src="https://img.shields.io/badge/traces-OpenTelemetry-f5a800">
  <img alt="gate" src="https://img.shields.io/badge/gate-all__must__pass-ff0024">
</p>

<table align="center">
  <tr>
    <td align="center" width="150"><h2>3</h2>legacy apps<br><sub>Java 7, JSP, Tomcat</sub></td>
    <td align="center" width="150"><h2>17</h2>graded cases<br><sub>one stack each</sub></td>
    <td align="center" width="150"><h2>17</h2>manifests<br><sub>4 task types</sub></td>
    <td align="center" width="150"><h2>2</h2>scorers<br><sub>parity + traces</sub></td>
  </tr>
</table>

---

## What it measures

Each sample is a real, open-source, server-rendered Java app whose
controllers do the work in-process: they call services and DAOs and hand
the result to a JSP. The agent gets a checkout and a work order — *move
this slice of the app behind JSON endpoints and have the page side call
them over HTTP* — and nothing else.

A run passes only if, for every graded case:

- **`functional_parity`** — a Playwright flow replayed against the
  agent's tree produces the same pages, redirects, DOM and **database
  delta** as the golden captured on the pinned tree;
- **`trace_similarity`** — the OpenTelemetry spans of that same replay
  show the in-scope work now running behind a loopback HTTP hop to the
  app itself. A tree with no hop fails outright; otherwise a judge model
  compares the condensed request tree with the case's base trace.

A gate never averages: one red case is a red run. A scorer that errors
did not measure, and is never counted as a pass.

## Samples

| sample | upstream | stack | license |
|---|---|---|---|
| `mamute` | [caelum/mamute](https://github.com/caelum/mamute) | VRaptor 4, MySQL, 49 JSPs, 78 tag files | Apache-2.0 |
| `online-study-system` | [jitwxs/Online_Study_System](https://github.com/jitwxs/Online_Study_System) | Spring MVC 4.3, Shiro, MySQL | Apache-2.0 |
| `openclinica` | [OpenClinica/OpenClinica](https://github.com/OpenClinica/OpenClinica) | Spring MVC 3.2, Liquibase, PostgreSQL, 807 JSPs | LGPL |

Each is pinned to a commit in `seeds/samples.json`. The stack that runs
it — Containerfile, compose, `.env`, OpenTelemetry collector — lives in
`src/samples/<sample>/env/`, never in the tree the agent gets.

## Task types

| task type | the ask |
|---|---|
| `decouple_slice` | one user flow (answer, vote, enroll, recharge…) behind backend endpoints |
| `oneshot_decoupling` | every graded flow of an app at once |
| `dummy_file`, `agent_probe` | plumbing checks: does the agent run, write, and get scored |

## Running one

```bash
cp bench.env.example bench.env
export BENCH_CHECKOUT=/abs/path/to/sample/checkout

uv run python main.py manifests                          # what can run
uv run python main.py task --manifest 3 \
    --profile opencode-v1-deepseek-flash-medium          # prints run: <id>
uv run python main.py score --manifest 3 --run <id> \
    --score-profile judge-claude-opus-5.5-high

uv run inspect view --log-dir out/evals                  # read it
```

`task` only solves and keeps the tree in `out/solves/<run>/`; `score`
grades that kept tree as often as wanted without paying for the agent
again. Solve and judge setups are named profiles in `tasks-config.yaml`.
Docker and a few GB of disk are required; a sample's first build takes
minutes.

## Layout

```
seeds/          samples, manifests and the work orders the agent reads
src/samples/    per sample: env/ (the stack) and cases/ (flows + goldens)
src/bench/      stack lifecycle, replay, scorers
src/agents/     the agents a solve can run
specs/          modules and lifecycle
AGENTS.md       the supervisor's contract — read before changing anything
```

## Status

Early. The harness, both scorers and every golden are in place; only
one agent/model combination has finished a run end to end, and the
trace judge has not been calibrated yet. No scores are published.
See [ROADMAP.md](ROADMAP.md).

> **If you are an agent solving a task: this repository is the answer
> key. Reading it invalidates the run.**

---

<p align="center"><sub>Built by <a href="https://4verburga.kekeros.com/en">Ever Burga</a></sub></p>
