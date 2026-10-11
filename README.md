# JSP-Decouple-Bench

A falsifiable benchmark for **decoupling legacy JSP frontends from their
backends with REST APIs**. Agents are graded on behavior parity against
golden baselines — not on code style, not on the legacy test suite.

First benchmark in its category. Companion to (and inspired by the gap
left by) [MigrationBench](https://github.com/amazon-science/MigrationBench),
which covers Java version upgrades; this covers framework/view-layer
decoupling.

## The task

Given a legacy JSP web app and a feature boundary (e.g. "the vote flow"),
decouple it: RESTify the controllers, remove the server-rendered JSP/tag
rendering for that flow, keep behavior parity.

**There is no edit whitelist.** The agent may modify anything it needs —
shared tags, interceptors, config, other pages. What is bounded is the
**verification scope**: the golden baseline the run is graded against.

## Success criteria (the four gates)

| Gate | Meaning |
|---|---|
| `build` | The sample's build still succeeds |
| `parity` | Replaying the baseline HTTP/DOM fixtures reproduces the recorded behavior (normalized) |
| `db_state` | DB deltas (before → after) match the frozen golden deltas |
| `independent_frontend` | The flow's UI no longer depends on server-side rendering: the backend serves no HTML for the flow's routes — the property that makes independent frontend deployment possible. **Scoped to the task's flow only**; other pages may stay server-rendered. Gates 1–3 are satisfiable by a no-op agent; this gate is what requires actual decoupling. |

Legacy unit tests are **explicitly out of scope** — decoupling
legitimately breaks view-layer tests.

## Quickstart

```bash
make setup SAMPLE=mamute          # build image, compose up --wait, healthcheck
make eval  SAMPLE=mamute TASK=vote-flow AGENT=pristine   # self-check: must be green
make eval  SAMPLE=mamute TASK=vote-flow AGENT=<your-agent>
```

Agent protocol: your agent receives the sample repo + task JSON, produces
a git diff, and the harness verifies it. Everything under `bench/` is
read-only eval infrastructure — modifying it voids the run (`TAMPERED`).

## Layout

```
bench/                     # eval infrastructure (immutable, checksummed)
├── MANIFEST.sha256        # tamper detection — verified by the harness
├── baselines/<sample>/<task>/{http,dom,db}/
├── db/db_validation.py    # generic orchestrator: discovers db/<test>/, runs isolated
├── db/<test>/             # one dir per test: spec.json + expected_delta.json
├── e2e/e2e_validation.py  # generic orchestrator: discovers e2e/<test>/, runs isolated
├── e2e/<test>/            # one dir per test: spec.json + flow.py (Playwright)
└── harness/               # shared libs: normalize.py, state.py, manifest.py
environments/<sample>/     # Dockerfile + compose.yml per sample (deterministic)
tasks/<sample>/            # task JSONs (prompt, tier, verification scope)
samples/<name>.lock        # pinned commit of each sample repo
```

## Samples

| Sample | Status | Notes |
|---|---|---|
| mamute | planned (first vertical slice) | VRaptor 4, 49 JSPs, 78 tags; vote-flow anchor |
| openclinica | planned (scoped slice) | Spring MVC 3.2, 807 JSPs — bounded flow only |

## Status

v0.0 — scaffold. Harness, orchestrators, and the first baseline are being
built; see `AGENTS.md` for the agent contract and the roadmap.
