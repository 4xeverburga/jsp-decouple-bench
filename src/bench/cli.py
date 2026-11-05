"""The bench's command line: `python main.py <verb>`.

One manifest takes two `inspect eval` runs, from two verbs: `task` lets the
agent work in the workspace built for it, and `score` grades the tree it
kept, whenever and as often as wanted. They are apart because the agent
needs an Inspect sandbox and the scorer does not: it starts the app's stack
itself, from the host. What two processes cannot hand each other is ours,
and it is all this file is:

- a run id, which names `out/solves/<id>/`;
- the checkout the scoring phase needs, derived from that id, so a stale
  one cannot quietly grade the previous run's tree;
- the solve workspace, cut from the pin, which must carry no stack file.

Everything else is Inspect's own CLI (`inspect view`, `inspect log`) or
ruff, and `specs/behavior.md` shows the two commands by hand.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from dotenv import dotenv_values
from inspect_ai.log import list_eval_logs, read_eval_log

import settings

from . import capture as freezing
from . import solves
from .compose import sample_env, solve_compose
from .seeds import manifest as load_manifest
from .seeds import manifests as all_manifests
from .seeds import pin

TASKS = settings.ROOT / "main.py"


def _tool(name: str) -> list[str]:
    """A console script this venv provides, or uv as the fallback."""
    found = shutil.which(name)
    return [found] if found else ["uv", "run", name]


def _eval(
    spec: str,
    args: list[str],
    logs: str,
    env: dict[str, str],
    model: str,
) -> str:
    """One `inspect eval`; `model` is the eval's model. Returns its attempt.

    `model` is not what answers a solve's calls: the task builds that
    model itself, from the profile, with the profile's effort and
    arguments.

    The attempt is a fresh id, written to the log's eval metadata, and the
    only thing that tells this invocation's log apart: two scores of one
    run — side by side, or today's and last week's — share every task
    argument.
    """
    attempt = uuid.uuid4().hex
    argv = [
        *_tool("inspect"),
        "eval",
        spec,
        *args,
        "--metadata",
        f"attempt={attempt}",
        "--model",
        model,
        "--display",
        "plain",
        "--log-dir",
        logs,
    ]
    subprocess.run(
        argv, cwd=settings.ROOT, env={**os.environ, **env}, check=True
    )
    return attempt


def _require_success(logs: str, attempt: str, run: str, phase: str) -> None:
    """Stop unless the eval `attempt` names finished as a success.

    `inspect eval` exits 0 when a task errors or is interrupted, and a
    solve's cleanup still keeps the untouched tree. Scoring that tree would
    grade an agent that never ran as one that changed nothing, so a phase
    that did not succeed ends the run here, with Inspect's own reason.

    The log is found by its attempt, not by run and phase: those are
    shared by every score of one run, so they could name another one's.
    """
    for info in list_eval_logs(logs):
        header = read_eval_log(info, header_only=True)
        if header.eval.metadata.get("attempt") == attempt:
            if header.status == "success":
                return
            reason = header.error.message if header.error else header.status
            raise SystemExit(
                f"{phase} of run {run} did not succeed ({header.status}): "
                f"{reason}; log: {info.name}"
            )
    raise SystemExit(
        f"no {phase} log for run {run} (attempt {attempt}) in {logs}"
    )


def _spec(manifest_id: int) -> str:
    """The `@task` this manifest is graded by: its own type, by name."""
    chosen = load_manifest(manifest_id)
    return f"{TASKS.name}@{chosen['task_type']}"


def _build_toolbox(slug: str, workspace: Path) -> None:
    """Build the solve image, which carries the sample's Maven cache.

    `docker compose up` (what the sandbox runs) never rebuilds an image that
    already exists, and the first build of a toolbox downloads that whole
    cache: minutes, inside an eval whose sandbox startup has a timeout of its
    own. Building it here streams the download where it can be watched, and
    leaves the run with the image its `toolbox/Containerfile` describes.
    """
    subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(solve_compose(slug)),
            "build",
            "workspace",
        ],
        env={
            **os.environ,
            "BENCH_CHECKOUT": str(workspace),
            "BENCH_SAMPLE_ENV": str(sample_env(slug)),
            "SOLVE_ROOT": settings.SOLVE_ROOT,
        },
        # stdout belongs to the driver (`run: <id>`); a build is chatter.
        stdout=sys.stderr,
        check=True,
    )


def solve(manifest_id: int, profile: str, run: str, logs: str) -> None:
    """Let the profile's agent work on a tree cut from the pin.

    The task resolves the profile itself, from `tasks-config.yaml`; this
    process resolves it too, because only it can hand the provider's
    credentials to `inspect eval` and name the model that answers.
    """
    resolved = settings.solve_profile(profile)
    chosen = load_manifest(manifest_id)
    slug = chosen["sample"]
    workspace = solves.materialise(Path(settings.checkout()), pin(slug))
    try:
        _build_toolbox(slug, workspace)
        attempt = _eval(
            _spec(manifest_id),
            [
                "-T",
                f"manifest_id={manifest_id}",
                "-T",
                "phase=solve",
                "-T",
                f"run={run}",
                "-T",
                f"profile={profile}",
            ],
            logs,
            {
                "BENCH_CHECKOUT": str(workspace),
                "BENCH_SAMPLE_ENV": str(sample_env(slug)),
                "SOLVE_ROOT": settings.SOLVE_ROOT,
                **settings.credentials(resolved),
            },
            resolved["answer_model"],
        )
        _require_success(logs, attempt, run, "solve")
    finally:
        _discard(workspace.parent)


def _discard(path: Path) -> None:
    """Remove a run's temporary directory, best effort.

    The sandbox writes as root over the bind mount (logs/, target/), so
    the removal can hit files this user cannot unlink. The kept tree,
    the diff and the record are already written when this runs, so a
    leftover directory is residue, not a lost run — say so and move on
    instead of failing a run that succeeded.
    """
    try:
        shutil.rmtree(path)
    except (PermissionError, FileNotFoundError) as error:
        print(f"warning: {path} not fully removed: {error}", file=sys.stderr)


def score(manifest_id: int, run: str, score_profile: str, logs: str) -> None:
    """Grade the tree a solve kept; the replay starts the stack itself.

    The score profile names the judge `trace_similarity` asks; its
    credentials come from `bench.env`, like a solve profile's. The task labels
    the log with the solve profile from the run's record.
    """
    judge = settings.score_profile(score_profile)
    tree = solves.tree(run)
    if not tree.is_dir():
        raise SystemExit(f"no tree for run {run}: {tree} is missing")
    # What produced this tree, from the run's own record: a re-score of last
    # week's run must not be labelled with today's `bench.env`.
    record = solves.read(run)
    if "profile" not in record:
        raise SystemExit(
            f"run {run} predates run profiles: its record names no profile, "
            f"so its score cannot be labelled with one; solve it again"
        )
    slug = load_manifest(manifest_id)["sample"]
    env_dir = sample_env(slug)
    credentials = dotenv_values(env_dir / ".env")
    attempt = _eval(
        _spec(manifest_id),
        [
            "-T",
            f"manifest_id={manifest_id}",
            "-T",
            "phase=score",
            "-T",
            f"run={run}",
            "-T",
            f"profile={score_profile}",
            # Cases replay side by side: each stack picks its own port,
            # and `stack.running` bounds how many are up on the host.
            "--max-samples",
            str(settings.SCORE_MAX_SAMPLES),
        ],
        logs,
        {
            **{k: v for k, v in credentials.items() if v is not None},
            **settings.credentials(judge),
            "BENCH_CHECKOUT": str(tree),
        },
        settings.SCORE_MODEL,
    )
    _require_success(logs, attempt, run, "score")


def capture(manifest_id: int, cases: list[str]) -> None:
    """Freeze a manifest's goldens from its pinned tree.

    `BENCH_CHECKOUT` names the sample's repository here, as it does for
    `task`: the pin is cut from it and only then becomes the tree the
    stack builds. Each case's stack picks its own port, as in scoring; the
    golden does not record it, because parity normalizes the base URL out
    and the span condenser erases hosts.
    """
    chosen = load_manifest(manifest_id)
    slug = chosen["sample"]
    wanted = cases or list(chosen["scope"]["cases"])
    unknown = sorted(set(wanted) - set(chosen["scope"]["cases"]))
    if unknown:
        raise SystemExit(f"manifest {manifest_id} has no case(s): {unknown}")
    commit = pin(slug)
    tree = solves.materialise(Path(settings.checkout()), commit)
    previous_checkout = os.environ.get("BENCH_CHECKOUT")
    try:
        # From here the stack must build the pinned tree, not the worktree
        # the pin came from — same env the scorer is given. The address is
        # each stack's own, as in scoring.
        os.environ["BENCH_CHECKOUT"] = str(tree)
        credentials = dotenv_values(sample_env(slug) / ".env")
        for key, value in credentials.items():
            if value is not None:
                os.environ[key] = value
        freezing.run(slug, wanted, commit, chosen["bindings"]["db"]["options"])
    finally:
        if previous_checkout is None:
            os.environ.pop("BENCH_CHECKOUT", None)
        else:
            os.environ["BENCH_CHECKOUT"] = previous_checkout
        _discard(tree.parent)


def _capture_verb(args: argparse.Namespace) -> None:
    capture(args.manifest, args.case)


def _task(args: argparse.Namespace) -> None:
    # Always a fresh id: a reused one would wipe the earlier run's
    # workspace and overwrite its kept tree and record.
    run = uuid.uuid4().hex
    print(f"run: {run}", flush=True)
    solve(args.manifest, args.profile, run, args.logs)
    print(f"tree: {solves.tree(run)}")


def _score_verb(args: argparse.Namespace) -> None:
    score(args.manifest, args.run, args.score_profile, args.logs)


def _manifests(_args: argparse.Namespace) -> None:
    for row in all_manifests():
        cases = len(row["scope"]["cases"])
        scorers = ",".join(row["scorers"])
        print(
            f"{row['id']:>3}  {row['name']:<24} {row['task_type']:<18} "
            f"{cases} case(s)"
        )
        print(f"     scorers: {scorers}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Solve a manifest; score what a solve left, later.",
    )
    verbs = parser.add_subparsers(required=True)

    task = verbs.add_parser(
        "task", help="solve one manifest; prints the run id to score"
    )
    task.set_defaults(handler=_task)
    task.add_argument("--manifest", type=int, required=True)
    task.add_argument(
        "--profile",
        required=True,
        help="who solves it: a solve_profiles entry of tasks-config.yaml",
    )
    task.add_argument(
        "--logs", default=str(settings.LOGS), help="Inspect log dir"
    )

    graded = verbs.add_parser("score", help="grade a tree a solve kept")
    graded.set_defaults(handler=_score_verb)
    graded.add_argument("--manifest", type=int, required=True)
    graded.add_argument("--run", required=True)
    graded.add_argument(
        "--score-profile",
        required=True,
        help="who judges it: a score_profiles entry of tasks-config.yaml",
    )
    graded.add_argument(
        "--logs", default=str(settings.LOGS), help="Inspect log dir"
    )

    frozen = verbs.add_parser(
        "capture", help="freeze a case's golden from the pinned tree"
    )
    frozen.set_defaults(handler=_capture_verb)
    frozen.add_argument("--manifest", type=int, required=True)
    frozen.add_argument(
        "--case",
        action="append",
        default=[],
        help="case id; repeatable, default is every case of the manifest",
    )

    listed = verbs.add_parser("manifests", help="list them and their cases")
    listed.set_defaults(handler=_manifests)
    return parser


def main(argv: list[str]) -> None:
    args = _parser().parse_args(argv)
    args.handler(args)
