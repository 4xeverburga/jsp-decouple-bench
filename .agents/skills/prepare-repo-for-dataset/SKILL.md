---
name: prepare-repo-for-dataset
description: >
  Prepare a legacy project repo to become a benchmark dataset sample:
  protect the git history (never rewrite or force-push main, keep the
  original upstream commits reachable on the remote so provenance can be
  traced) while keeping every pointer to that origin out of the tree the
  agent reads, and leave the project runnable (old projects need old
  toolchains — don't modernize dependencies for convenience, keep the
  runbook verified). Use when asked to "prepare this repo for the
  dataset", "make this project a sample", or before starting any
  authoring work (bench tests, baselines, environments) on a candidate
  repo.
---

# Prepare a repo for the dataset

Run this **before any authoring work** on a candidate repo (before
`authoring-bench-tests`, before baselines, before environments). It
establishes the two invariants every later phase depends on: traceable
history and a runnable project.

## 1. Protect the history (provenance)

The dataset's value depends on being able to trace every change back to
the pristine upstream state. A rewritten history destroys that.

- **Enforce it with GitHub branch protection — literally.** Discipline
  is not protection. On the sample's GitHub repo, set up a branch
  protection rule (or ruleset) for `main` that **disallows direct
  pushes**, blocks force pushes, and blocks deletions, so every change
  lands via a PR (the owner can merge their own PR with 0 required
  approvals — the point is that `git push origin main` is rejected, not
  that a second human reviews). Via the UI: Settings → Branches → Add
  branch protection rule → "Require a pull request before merging" (0
  approvals) + "Do not allow force pushes" + "Do not allow deletions".
  Via `gh` (needs admin on the repo):
  ```bash
  gh api -X POST repos/<owner>/<repo>/rulesets \
    -f name='protect-main' -f target='branch' -f enforcement='active' \
    -f 'conditions[ref_name][include][]'='refs/heads/main' \
    -f 'rules[][type]'='pull_request' \
    -f 'rules[][parameters][required_approving_review_count]'=0 \
    -f 'rules[][parameters][dismiss_stale_reviews_on_push]'=false \
    -f 'rules[][parameters][require_code_owner_review]'=false \
    -f 'rules[][type]'='non_fast_forward' \
    -f 'rules[][type]'='deletion'
  ```
  Verify it is active (`gh api repos/<owner>/<repo>/rulesets` lists it,
  or a test `git push origin main` is rejected). **If you lack admin
  access, stop and ask the user to enable it** — do not start authoring
  on an unprotected `main`.
- **Never force-push, never rewrite `main`.** No `commit --amend` on
  pushed commits, no `rebase`/`filter-branch`/`filter-repo` on shared
  branches, no history squashing. If a mistake is already pushed, add a
  new commit that fixes it — a noisy history is fine; a lost one is not.
- **Tag the pristine HEAD first**, before any change:
  ```bash
  git tag pristine && git push origin pristine
  ```
  This tag preserves the original upstream provenance; it is not a harness
  or a runtime selector. Benchmark runs and captures use the sample's pinned
  `commit_sha`, which is seed data in `seeds/sources.json` and reaches
  `bench.db` only through `make db-init`. If the repo is a
  HEAD-only upstream mirror, this single commit IS the provenance anchor —
  treat it as immutable.
- **Work on feature branches, merge with merge commits** into `main`
  (`git merge --no-ff`). No squash merges, no fast-forward-only flows —
  the point-by-point history of how the sample was built is part of the
  dataset's documentation.
- **Push everything before declaring done**: branches, `main`, and tags.
  Local-only commits are invisible to anyone auditing the sample later.
- **Do not point at the origin from inside the tree.** The history is the
  provenance: the `pristine` tag, the remote, and `SAMPLE.project_id` in
  `seeds/sources.json`. The checkout an agent reads must say nothing about
  where the code came from — no `UPSTREAM.md`, no upstream URL in README /
  AGENTS.md / `pom.xml` `<scm>`, no "mirror of" sentence, no release-war
  download, no update script that curls the project site. One link is
  enough for an agent to fetch the original project and start reasoning
  about today's code as somebody else's legacy app, which is exactly the
  outside knowledge the eval exists to exclude.
  ```bash
  git grep -InE 'github\.com/<owner>|upstream|@<upstream-domain>' -- .
  ```
  must be empty. Three exemptions, and only these: `LICENSE` (the
  attribution Apache-2.0 requires), code identity — Java packages and
  Maven `groupId` like `br.com.<owner>.*` (renaming them breaks the build,
  and a namespace is not a navigation aid), and rendered product branding
  (footer link, `og:site_name`, mail templates), which lives in the graded
  markup: scrubbing it means recapturing every golden of the sample, so
  decide it deliberately and do it in one change.
- **Keep the build inputs**: `local-repo/`, pinned vendored artifacts and
  committed toolchain files stay in the repo — they are what makes the
  sample build, not references to its origin.
- **The pin carries no stack file.** The stack (compose, Containerfile,
  `.env`, the collector) is the harness's and lives in the bench under
  `src/samples/<sample>/env/`; a copy in the tree tells the agent how the
  app is run — service names, the database host, the image its toolchain
  comes from. Delete them in the sample repo and re-pin; never expect the
  runner to strip them, because it refuses a tree that still has one
  (`solves.materialise`) rather than quietly grading a leaked sample.
  ```bash
  git ls-tree -r --name-only HEAD | grep -Ei \
    '(^|/)(.*ockerfile|(docker-)?compose([.-].*)?|entrypoint\.sh|\
  bootstrap\.sh|\.env)$'
  ```
  must be empty. Three files are **not** stack files and stay:
  `.dockerignore` (the build context *is* this tree, so it is what keeps
  `target/` and `node_modules/` out of the image), `.env.example`, and the
  app's own `*.properties.example` templates — setup documentation with no
  secrets, which the runbook depends on.
- **Nothing in the tree may name the bench.** Provenance is one kind of
  tell; vocabulary is the other. The checkout is read by an agent that
  must not know it is being measured, so any phrase that describes the
  harness, the grading or the work itself is a leak even when it names no
  origin. Scrub, in this order of severity:
  - **the task**: comments like `# the task: remove this`, `# dropping
    data from front is the task`, `ADAPT` markers, "what the gate reads
    from this file". They hand over the answer and the grading, not just
    the fact of an eval;
  - **the harness**: "eval environment", "sample", "harness exports
    it", "the bench repo", "make pin", "golden", "graded";
  - **variable names**: a sample publishes its host port from a neutral
    name (`APP_HTTP_PORT`, `APP_DB_PORT`), never one named after the
    thing that exports it — `BENCH_HTTP_PORT` in a `compose.yaml` tells a
    reader a runner sets it per run;
  - **credentials**: a tracked synthetic password may not contain
    `bench` either (`.env` is read as a file, not through a runner).
  ```bash
  git grep -InE 'BENCH_|eval (environment|sample)|the bench|bench (repo|\
  convention|password)|harness|golden|graded|decoupl|the task' -- .
  ```
  must be empty apart from upstream code that happens to use the words
  (`evaluate`, `Task`, vendored `benchmark/` dirs). Remember the template
  and every copied file land in this tree: `templates/compose.template.yaml`
  and `templates/README.md` may carry authoring instructions, but the
  `compose.yaml` you commit may not — keep the copied file reading like a
  normal application's compose file. Re-pin after scrubbing (`make
  db-init` picks the new `commit_sha` up from `seeds/sources.json`); a
  scrub that is not in the pinned commit changes nothing for the agent.
- **The pin must be the tip of its branch, and its history must be
  unreachable.** Provisioning clones **one commit deep** (`--depth 1
  --branch <branch>`) into the run's sandbox, so the checkout has no
  remote, no refs, no reflog **and no parent objects**. A detached HEAD
  is not enough on its own: every commit object names its parent, and a
  full clone keeps the ancestors on disk, so `git log` still walks the
  whole history — including the commit that says it is an eval sample.
  Consequence for authoring: put the pin at a branch tip (push a branch
  that points at it), because a shallow clone cuts at a ref.
  ```bash
  # in the run's checkout: 1 commit, shallow, and the parent is gone
  git rev-list --count HEAD                 # 1
  git rev-parse --is-shallow-repository     # true
  git cat-file -e <parent-of-HEAD>          # fails: bad object
  ```
  `provision()` refuses a clone that is not shallow, so a mistake here
  fails loudly instead of scoring a tainted run.

## 2. Leave the project runnable

Old projects have old dependencies. The sample must keep building and
running exactly as the legacy app did — the pristine baseline and every
agent eval depend on the environment behaving identically.

- **Do not upgrade dependencies "while you're in there".** No version
  bumps, no framework swaps, no build-plugin updates — even ones that
  look safe. Legacy toolchains are pinned for a reason (e.g. JDK 8 for
  Java 7 source/target, MySQL 5.7 for an old connector, PostgreSQL 9.6
  for a pre-SCRAM driver). An upgrade silently changes behavior and
  invalidates captured baselines.
- **Keep the runbook verified.** The sample's `AGENTS.md` quick-start
  must be copy-paste correct on this machine: build, boot, healthcheck.
  Re-run it after your changes; fix drift you find (wrong paths, stale
  ports, missing steps) rather than leaving it to the next person.
- **Verify the app still runs after every change session**: build green,
  app boots, the healthcheck/home URL answers. "It compiled" is not
  "it runs".
- **Machine-specific stuff stays out of tracked files**: local paths,
  ports, credentials go in `AGENTS.md` (documented, machine-specific
  sections are fine there) or gitignored files — never hardcoded into
  build files or source. Gitignore local build artifacts you generate
  (log dirs, exploded WARs, generated assets) so the tree stays clean.
- **Don't break the vendored/offline story**: if the project vendors
  dependencies (`local-repo/`, checked-in jars, generated web assets
  that are gitignored but regenerable), keep those steps documented and
  working — a fresh clone must reach a running app via the runbook.

### The stack shape (compose template)

Every sample commits the same stack shape at its pin, copied from
`templates/compose.template.yaml` in the bench repo and adapted. It is
what makes `network_isolation` a real assertion instead of a description
of whatever the app happens to look like.

- **One repository, one application.** `front` and `back` are built from
  the same context. The sample is not two projects: it is one app whose
  data side can be isolated, so the frontend can be refactored later
  without the data side moving.
- **Keep the names**: services `front`, `back`, `db`; networks `api`
  (`front` <-> `back`) and `data` (`back` <-> `db`). The gate's
  vocabulary is these names; inventing new ones breaks the contract.
- **At the pin, `front` is attached to BOTH `api` and `data`.** The
  pristine app is server-rendered and reaches the database directly, so
  the isolation assertion must be **false** on the pinned commit. If you
  "fix" it while preparing the sample, the sample has no task left in it
  and the gate is vacuous. `dataset-ready-check` §2 verifies this.
- **Only `front` publishes a host port.** The harness reads the database
  with `compose exec`, so every extra published port is surface with no
  purpose. Publish it from `APP_HTTP_PORT` (a neutral name — see §1 on
  vocabulary), never from a name that mentions the runner.
- **No `network_mode:`**, neither `host` nor `service:`.
- **Add services, never networks.** A collector or sidecar joins `api` or
  `data`; a new top-level network is a contract change and belongs in the
  template first.
- **Commit it at the pin** before any golden is captured: the gate reads
  the contract from `git show <commit_sha>:compose.yaml`, never from the
  worktree, so the file must be in the pinned commit.

## 3. Install the OpenTelemetry agent (trace base)

`trace_similarity` compares the traces of a finished run with a base taken
from the pristine app, so every sample must be able to emit them. The
sample must have the **OpenTelemetry Java agent** installed **before** its
pin is created and before any golden or trace base is captured: the agent
is part of the pinned environment, not an afterthought.

- **Attach it from outside the app.** Add the agent in the sample's
  `Dockerfile` / `compose.yaml` (JVM flag `-javaagent:` through the
  variable the app's launcher honours — e.g. `JAVA_TOOL_OPTIONS`, or
  `MAVEN_OPTS` when the app runs via `mvn exec:java`, since that is the
  JVM that hosts it). Do not touch `pom.xml`, app source or app
  dependencies: this is instrumentation, not a dependency upgrade.
- **Pin and vendor it.** Exact agent version and `sha256` verified at
  image build; no download at boot. A fresh clone must still reach a
  running app offline after the first image pull. The app's runtime must
  be supported by the agent (Java 8+); if not, record that in the
  assessment and stop — the sample cannot feed `trace_similarity`.
- **Configure only through `OTEL_*` variables** in the sample's `.env`
  (tracked, synthetic) and document them in `.env.example`:
  `OTEL_SERVICE_NAME=<sample slug>`, `OTEL_TRACES_SAMPLER=always_on`,
  `OTEL_METRICS_EXPORTER=none`, `OTEL_LOGS_EXPORTER=none`, and the traces
  exporter/endpoint. For the spans the oracle needs beyond HTTP, JDBC and
  JSP render (all automatic), list the controller/DAO methods via
  `OTEL_INSTRUMENTATION_METHODS_INCLUDE`.
- **Declare every moving part in `compose.yaml`.** A collector or sidecar
  is a service of the sample's own stack, attached to `api` or `data` and
  publishing no port, so `network_isolation` keeps passing. It never joins
  `host` and never adds a network.
- **Fail open and change nothing observable.** The app must boot and
  pass its healthcheck with the collector down, and the no-op
  `functional_parity` run must stay green with the agent attached.
- **Deterministic.** Same flow, same span tree shape (names, parentage,
  `http.method`/route); only ids and timestamps vary.
- Document in the sample's `AGENTS.md` how to see spans locally.

The trace adapter that writes `out/runs/<run_id>/traces.json` is not
implemented yet (ROADMAP §2.3); until it is, `trace_similarity` stays
`pending`. Installing the agent now means the base exists the day it
lands. `dataset-ready-check` §7 verifies it.

## 4. How benchmark runs execute an agent

The agent adapter is selected per run by the command the run is given
(`HARNESS_CMD`, prompt on stdin); `HARNESS` is only the label the run is
recorded under. The runner clones **one commit deep** from the local mirror
(`git clone --no-local --depth 1 --branch <branch>`) into the sandbox the
run owns, then detaches, scrubs refs/reflog and refuses to start if the
result is not shallow or still reaches a parent commit. It does not stash
or discard changes.

After the sample is wired into the registry and its cases are ready, pin the
commit to evaluate and launch a task:

```bash
# 1. set sample.commit_sha in seeds/sources.json, then:
make db-init
# 2. run from a folder that exists only for this run (absolute, empty)
make task MANIFEST_ID=<n> SAMPLE_SANDBOX=<abs empty folder> \
  HARNESS=claude-code
make gate GATE_ID=functional_parity RUN_ID=<run_id>
```

`make task` prints the `run_id`; a run itself has no pass/fail verdict.
Evaluate gates separately, as independent measurements. For the no-op
self-check, use `HARNESS=command HARNESS_CMD=true`; run this only after the
sample's benchmark cases and environment have been authored. A `command`
harness that launches a real agent requires its command via `HARNESS_CMD`.

### Scoping the tree is not isolation

The agent runs as the supervisor's user, so everything that user can read is
in reach: `$HOME` (this repository, `bench.db`, the cases), `/tmp` (whatever
the last command left there), shell history, and the agent's own store from
earlier runs. Two runs were scored this way — one walked the sample's own
git ancestry, the next found a replay harness in the supervisor's `/tmp`
scratch and copied it.

Sandbox it at the layer that provisions the stack, not with a wrapper around
the agent. In the ported bench (`inspect_port/`) Inspect boots the compose
project and the agent runs inside that sandbox, which also removes the
docker socket from the agent's reach: the daemon is on the evaluator's side,
so `docker run -v /:/host` is not available to it.

The old approach — a bwrap mount namespace around `HARNESS_CMD` — was
deleted with the port rather than kept in parallel. What still needs
auditing is the network: a sandbox hides files, not reachable services.
`audit-agent-trace` looks for that.

## Checklist (all must be true before authoring starts)

- [ ] GitHub branch protection/ruleset active on `main`: direct pushes
      rejected, force pushes and deletions blocked (verified, not
      assumed).
- [ ] `pristine` tag exists on the upstream HEAD and is pushed.
- [ ] `main` on the remote is untouched history (verify:
      `git log --oneline origin/main` matches local; no force-pushes).
- [ ] Current work is on a feature branch, not directly on `main`.
- [ ] No upstream pointer in the tree: `UPSTREAM.md` absent, no upstream
      URL, "mirror of" sentence, release download or update script
      (`git grep -InE 'github\.com/<owner>|upstream|@<upstream-domain>'`
      is empty apart from `LICENSE` and code namespaces); `LICENSE` and
      the build inputs are still there.
- [ ] No bench vocabulary in the tree: the grep in §1 for `BENCH_`,
      `eval environment`, `the bench`, `harness`, `golden`, `graded`,
      `the task` and `ADAPT` is empty apart from upstream code, the
      published port uses `APP_HTTP_PORT`, and no comment describes the
      grading or the work to be done.
- [ ] The pin is a branch tip, and a fresh provision of it is one commit:
      `git rev-list --count HEAD` is `1` in the run's checkout and
      `git rev-parse --is-shallow-repository` is `true`.
- [ ] Runbook in the sample's `AGENTS.md` re-verified end to end
      (build → boot → healthcheck) on the current tree.
- [ ] No dependency versions changed (`git diff` on build manifests is
      empty apart from intentional, documented changes).
- [ ] `compose.yaml` follows `templates/compose.template.yaml`: services
      `front`/`db` (plus `back` when the work lands), networks `api` and
      `data`, only `front` publishes, no `network_mode:`, and at the pin
      `front` is attached to **both** `api` and `data`.
- [ ] The stack shape is in the pinned commit: `git show
      <commit_sha>:compose.yaml` renders, and on the pristine tree
      `network_isolation` **fails** while `functional_parity` passes.
- [ ] OpenTelemetry Java agent installed, version pinned and checksummed,
      configured via `OTEL_*` in `.env`, collector (if any) declared in
      `compose.yaml`, app still boots with it and with the collector
      down, and committed before `sample.commit_sha` is set.
- [ ] Working tree clean apart from intentional, committed changes;
      local artifacts gitignored.

## Anti-patterns

- Relying on discipline instead of enforcement — "I'll just be careful
  with `main`" is not protection; a future agent (or a tired human) will
  push to it. Set the GitHub rule and verify it rejects a direct push.
- Squash-merging the sample's construction "to keep history tidy" —
  tidiness is the enemy of provenance here.
- Upgrading a dependency because a build warning annoyed you — pin it,
  document it, move on.
- Leaving the runbook stale after changing ports/paths/credentials —
  the next person (or agent) loses hours to drift.
- Adding the OTel agent after goldens were captured, or by editing the
  app's `pom.xml`/source — it changes the pinned environment under
  existing goldens; install it first, from outside the app.
- Tidying the pin's `compose.yaml` so `front` no longer touches `data` —
  that deletes the task: a no-op run would then pass isolation, and the
  gate could no longer tell a working agent from one that did nothing.
- Committing generated artifacts that belong in `.gitignore`, or
  gitignoring things the runbook needs (e.g. tracked `.env` with
  synthetic credentials — see `authoring-bench-tests`).
- Believing a detached HEAD hides history. It hides the *names* (remote,
  branches, tags, reflog); the commit objects and their parents are still
  there, and one `git log` prints the commit message that says "eval
  sample". Only a shallow clone removes the ancestry.
- Shipping the template's authoring markers into the sample. `ADAPT`
  comments, "the gate reads this file", "the task: remove this" are
  written for whoever prepares the sample and are a giveaway to whoever
  reads it. Scrub them from the copied file, keep them in
  `templates/README.md`.
- Naming a sample's variables after the runner (`BENCH_HTTP_PORT`). A
  port name is documentation: it says who sets it and why.
