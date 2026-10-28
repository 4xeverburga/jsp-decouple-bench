# AGENTS — contract for a **supervisor** running this benchmark

This repository is the **supervisor's** side of the bench. The agent under
evaluation never sees it, and never learns that it is being evaluated.
If you are an agent that was handed a checkout and a prompt, this file is
not for you — you have no reason to be reading it.

## What the supervisor owns

| thing | where |
|---|---|
| registry of samples, manifests, runs, gates | `bench.db` (`schema.sql`, `seeds/`) |
| the prompts agents receive | `TASK_TYPE.base_prompt` + `TASK_MANIFEST.prompt` (seeds) |
| the graded behaviour (the answer key) | `src/gates/functional_parity/cases/` |
| the stack shape every sample commits | `templates/compose.template.yaml` |
| how to start / drive / inspect a sample | `src/env/` |
| how to run an agent | `src/harness/` |

## Running an agent

```bash
make task MANIFEST_ID=3 SAMPLE_SANDBOX=/abs/tmp/run-<id> \
          HARNESS=opencode-ds-flash-max \
          HARNESS_CMD='opencode run --auto --model opencode-go/deepseek-v4.1-flash#max "$$(cat)"'
make gate GATE_ID=functional_parity RUN_ID=<run_id>
```

There is no harness registry: `HARNESS_CMD` **is** the harness, the prompt
arrives on stdin, and it is required on every run — no agent command lives
in `.env`, so a stale one cannot outlive the model it was written for.
`HARNESS=<label>` selects nothing — it only names the run, so put the model
and its effort variant in the label when you intend to compare runs. Both
are recorded: the label in `TASK_RUN.harness`, the exact command line in the
run's `harness.json`.

## Hard rules

1. **Never expose this repository to the agent.** Not `bench.db`, not
   `seeds/`, not `specs/`, not `src/`, not `out/`. Provision a bare
   checkout of the sample and nothing else.
2. **A prompt is a work order, not an exam.** It must read as something a
   colleague or a ticket would say. No "benchmark", "golden", "parity",
   "case", "evaluation", no list of graded routes. What the agent reads is
   composed of two data fields: the task type's `base_prompt` (what this
   kind of work means and what it must not break — written once per type)
   and the manifest's `prompt` (which sliver of the app this run is about).
   Every run records both in `task.json`.
3. **Never leak scope.** Routes, case names, expected DB deltas and the
   golden artifacts are what the agent is judged on; they are not inputs.
   `harness.ports.HarnessTask` holds only `prompt` and `cwd` so this is
   enforced by construction — do not widen it.
4. **Do not brand the environment.** The `command` harness adds no
   environment variables; keep it that way. An agent that runs `env` or
   `pwd` must learn nothing about the bench.
5. **One folder, one run.** `SAMPLE_SANDBOX` is the folder allocated to
   **this** run (absolute path, absent or empty). The bench puts that run's
   single checkout in it and refuses a folder that already holds anything:
   nothing may sit beside the agent's tree, because a sibling is a place to
   look for the answer. Its **parent** must hold nothing but sandboxes —
   never `/tmp`, where every tool on the machine leaves files (build
   output, commit messages, a `bench.db` backup). The commit comes from the
   registry
   (`SAMPLE.source` + `SAMPLE.commit_sha`) through a bare mirror under
   `out/cache/<slug>.git` — never from a working copy. The clone is
   scrubbed before the agent starts: no remote, no branches, no tags, no
   reflog, so there is no history to mine either. The agent dirties its own
   tree freely afterwards, which is the point.
6. **Credentials come from the sample's `.env`.** Never hardcode them in a
   prompt, a case or a flow.
7. **Determinism.** `en-US`, `UTC`, `1280x800`, fresh DB per case. Do not
   introduce time-, locale- or host-dependent behaviour anywhere.
8. **Do not weaken the stack's declared shape.** `network_isolation`
   grades the pinned `compose.yaml` (`templates/compose.template.yaml`),
   never the worktree: `front` must stop sharing `data` with `db`, `db`
   stays on `data` alone, and only `front` publishes. The pin is
   deliberately non-conformant, so a no-op run must fail this gate.
9. **No defaults, no optional parameters.** No function may declare a
   default value or an optional parameter, and no code may carry a fallback
   literal for a tunable (`os.environ.get(k, "x")`, `or "x"`). Every
   tunable lives in `.env` (template: `.env.example`), is read once in
   `config.py`, and a missing key is an error. Callers pass every argument
   explicitly.
10. **PEP 8.** All Python follows PEP 8 (79 columns, `snake_case`,
    ordered imports); `pyproject.toml` configures `ruff` to enforce it.
    The Python version and dependencies are pinned there too: change them
    in `pyproject.toml`, nowhere else.
11. **Provenance stays out of the tree.** A sample's checkout must not
    name or link its origin — no `UPSTREAM.md`, no upstream URL, no
    "mirror of" sentence. Where it came from is `SAMPLE.project_id`, the
    remote and its history. A checkout that points at its source gives an
    agent outside knowledge the eval exists to exclude. `LICENSE` and
    package/`groupId` namespaces are the only exemptions.

## Trust nothing until the self-check is green

```bash
make task MANIFEST_ID=<n> SAMPLE_SANDBOX=$HOME/.bench-runs/run-<id> \
          HARNESS=command HARNESS_CMD=true
make gate GATE_ID=functional_parity RUN_ID=<run_id>     # must pass
```

A no-op command (`true`) leaves the tree untouched, so `functional_parity`
must reproduce every golden exactly. If that fails, the sample or the
environment is wrong and **no agent score on it means anything**.

`network_isolation` must **fail** on that same run: it grades the work,
not the behaviour. Parity green plus isolation red is the healthy pin.

## How a run is scored

Gates are independent and unordered; there is no composite score.

```bash
make gate GATE_ID=functional_parity RUN_ID=<run_id>
make gate GATE_ID=network_isolation RUN_ID=<run_id>
```

Each writes `out/runs/<run_id>/gates/<gate_id>.json`:

```json
{"gate_id": "functional_parity", "gate_version": 1, "run_id": "3f2c…",
 "value": 1.0, "verdict": "pass", "threshold": 1.0, "direction": "maximize",
 "duration_s": 812.4, "details": [{"case": "vote-flow__upvote-…", "verdict": "pass"}]}
```

- `verdict`: `pass | fail | error | pending` (exit codes 0 / 1 / 2 / 3).
- `value`: normalised to `[0,1]`, or `null` when the gate could not measure.
- A gate never averages: `pass` requires every sub-check to pass.

A run has no verdict of its own: it is finished when the harness returns.
Gates are independent measurements; combining them is the researcher's job.
`trace_similarity` reports `pending` until its oracle exists and is never
hand-scored.

Before a score is quoted — and always before two models are compared — the
run is audited with the `audit-agent-trace` skill: what the agent actually
read, whether any path left its checkout, and whether it ever reasoned
about being measured. `clean` is a claim about the trace; `unauditable` is
not a pass.
