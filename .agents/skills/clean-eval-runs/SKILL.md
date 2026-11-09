---
name: clean-eval-runs
description: 'Inspect, classify, and clean evaluation runs under out/. Use when asked to remove no-op results, failed or stale tasks, short runs, rate-limited runs, or associated run artifacts.'
---

# Cleaning evaluation runs

Use this workflow for requested cleanup of `out/` evaluation data. Default to
inspection and a deletion preview; do not delete files unless the user
explicitly requested cleanup.

## Scan

1. Check for active evaluations with `uv run inspect ctl task list`. Do not
   delete files that could belong to an active task.
2. Read eval files under `out/evals/` with `inspect_ai.log.read_eval_log`.
   Use `header_only=True` to inventory model, status, task arguments, and
   metadata. Read full logs only for candidates whose status or cause needs
   investigation.
3. Filter on the user's exact criterion and report the evidence for each
   candidate: eval path, model, phase, run, sample, manifest, status, duration,
   and relevant error or score details. Do not infer eligibility from a
   successful eval status alone: a sample can end at its time limit while the
   eval status is still `success`.
4. For duration filters, use the sample timing recorded in the log and state
   how the duration was calculated. For rate limits, distinguish solve from
   score failures. Retries alone do not prove rate limiting; verify an explicit
   rate-limit error or activity evidence, and check whether a later attempt
   succeeded before treating a run as invalid.

## Smoke and probe tasks

Smoke tests and probes (task types `dummy_file` and `agent_probe`, manifests
named `dummy-file*` and `agent-probe` in `seeds/manifests.json`) prove only
that an agent can act on a checkout. Their results are disposable, and unlike
real runs their solves are removable too, when the user asks to clean them.

1. Inventory both phases. Eval files are named after the task (`dummy-file`,
   `agent-probe`) and carry `phase: solve` or `phase: score`; find the
   manifests with `task_type` in those two from `seeds/manifests.json`
   instead of hard-coding names, because a sample can add its own
   (`dummy-file-openclinica`, ...).
2. Solves live in `out/solves/<run id>/`. Match a directory to the cleanup
   only through its `record.json`: `manifest_name` (or `manifest_id`) must
   be one of those manifests, and the run id must equal the directory name.
   Never match by directory age or by the eval file's date.
3. Remove each solve directory by its exact path, with the evals of that run
   (solve and score phases both) and the score artifacts of those evals, under
   the rules below. A run whose `record.json` has no manifest is a fixture,
   not a probe: leave it.
4. Show the preview as usual: eval files, solve directories and artifacts,
   with the manifest each was matched by.

## Runs killed or interrupted mid-solve

A solve that was stopped, or whose eval status is `started` with no samples,
leaves more than a log:

- The eval file has only `_journal/start.json`; there is no `out/solves/`
  directory for it. Check both before concluding the run is gone.
- The sandbox's compose project (`inspect-<task>-<id>`) keeps running.
  List it with `docker ps`, and stop it with
  `docker compose -p <project> down -v`, only for projects that belong to
  runs in scope. Do not touch projects that exited long before.
- Stop the driver process (`main.py task`) before deleting its eval: confirm
  with `uv run inspect ctl task list` and `pgrep -af "main.py task"`.
- Retry counts (`http_retries` in `inspect ctl task list`) suggest rate
  limiting but do not prove it; say which evidence was there.

## Preview and remove

1. Before deletion, present the exact eval files and any associated files to
   remove. If the criterion or scope is ambiguous, ask for clarification.
2. When removing score artifacts, use paths explicitly recorded in score
   metadata, such as `trace` and `screenshot`. Resolve each path and verify it
   is inside `out/traces/` or `out/evidence/` before considering deletion.
   Never remove shared case goldens or unrelated artifacts.
3. Remove only the exact, verified files in scope. Do not use broad recursive
   deletion, filename globs in destructive commands, or delete solve
   directories unless the user asked to remove those run records too and the
   association is verified.
4. Verify that every selected file is gone and rescan for remaining evals
   matching the criterion. Report counts and preserve unrelated worktree
   changes.
