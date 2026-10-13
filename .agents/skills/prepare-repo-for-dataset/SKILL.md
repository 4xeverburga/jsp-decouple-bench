---
name: prepare-repo-for-dataset
description: >
  Prepare a legacy project repo to become a benchmark dataset sample:
  protect the git history (never rewrite or force-push main, keep the
  original upstream commits reachable on the remote so provenance can be
  traced) and leave the project runnable (old projects need old
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
  Baselines are captured against this tag; every future re-capture or
  audit diffs against it. If the repo is a HEAD-only upstream mirror,
  this single commit IS the provenance anchor — treat it as immutable.
- **Work on feature branches, merge with merge commits** into `main`
  (`git merge --no-ff`). No squash merges, no fast-forward-only flows —
  the point-by-point history of how the sample was built is part of the
  dataset's documentation.
- **Push everything before declaring done**: branches, `main`, and tags.
  Local-only commits are invisible to anyone auditing the sample later.
- **Keep upstream references intact**: `UPSTREAM.md`, upstream URLs in
  README/AGENTS.md, and any vendored `local-repo/` or pinned artifacts
  stay in the repo — they are how a researcher re-derives the sample.

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

## Checklist (all must be true before authoring starts)

- [ ] GitHub branch protection/ruleset active on `main`: direct pushes
      rejected, force pushes and deletions blocked (verified, not
      assumed).
- [ ] `pristine` tag exists on the upstream HEAD and is pushed.
- [ ] `main` on the remote is untouched history (verify:
      `git log --oneline origin/main` matches local; no force-pushes).
- [ ] Current work is on a feature branch, not directly on `main`.
- [ ] `UPSTREAM.md` / upstream references present and accurate.
- [ ] Runbook in the sample's `AGENTS.md` re-verified end to end
      (build → boot → healthcheck) on the current tree.
- [ ] No dependency versions changed (`git diff` on build manifests is
      empty apart from intentional, documented changes).
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
- Committing generated artifacts that belong in `.gitignore`, or
  gitignoring things the runbook needs (e.g. tracked `.env` with
  synthetic bench credentials — see `authoring-bench-tests`).
