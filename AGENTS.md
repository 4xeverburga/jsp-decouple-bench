# AGENTS — Agent contract for JSP-Decouple-Bench

This file is the contract for any agent evaluated on this benchmark.

## What you receive

- A sample repo (pinned commit, vendored into the eval image) at
  `/workspace/<sample>`.
- A task JSON at `bench/tasks/<sample>/<task>.json` describing the
  feature boundary to decouple, its tier, and its verification scope.

## What you must do

Decouple the given feature boundary: RESTify the controllers, remove the
server-rendered JSP/tag rendering for that flow, keep behavior parity.

- **You may modify anything you need** — shared tags, interceptors,
  config, other pages. There is no edit whitelist.
- **The boundary is a verification scope, not an edit scope**: the
  golden baseline under `bench/baselines/` decides pass/fail.
- Leave your work as a git diff (the harness applies and verifies it).

## Hard rules

1. **`bench/` is read-only.** Everything under it is eval infrastructure,
   checksummed by `bench/MANIFEST.sha256`. Any modification → `TAMPERED`
   verdict. This includes baselines, orchestrators, and the harness.
2. **Legacy unit tests are out of scope.** Decoupling legitimately breaks
   view-layer tests. Do not spend effort resurrecting them; the four
   gates (build, parity, db_state, no_server_html) are the criteria.
3. **No network beyond the compose stack.** The environment is
   self-contained; external calls fail the run.
4. **Determinism**: the eval runs with pinned locale (`en-US`) and
   timezone (UTC). Do not introduce time- or locale-dependent behavior.

## How you are scored

`make eval SAMPLE=<s> TASK=<t> AGENT=<you>` runs the harness and emits
`verdict.json`:

```json
{
  "build": "pass",
  "parity": {"passed": 12, "total": 12},
  "db_state": "pass",
  "no_server_html": "pass",
  "tokens": 0,
  "files_touched": 0
}
```

Pass = all four gates green. Partial results are recorded per gate.

## Running the app locally

Each sample has `environments/<sample>/compose.yml`:

```bash
docker compose -f environments/<sample>/compose.yml up -d --wait
```

The app is up when the healthcheck passes; ports are fixed per sample
(see the sample's README).
