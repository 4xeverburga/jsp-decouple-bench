"""The bench's command line: `python main.py <verb>`.

One manifest takes two `inspect eval` runs — the agent in the workspace
built for it, then the scored tree — because the agent needs an Inspect
sandbox and the scorer does not: it starts the app's stack itself, from the
host. What two processes cannot hand each other is ours, and it is all this
file is:

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
from urllib.parse import urlsplit

from dotenv import dotenv_values

import settings

from . import capture as freezing
from . import solves
from .compose import sample_env, solve_compose
from .seeds import manifest as load_manifest
from .seeds import manifests as all_manifests
from .seeds import pin, sample

TASKS = settings.ROOT / "main.py"


def _tool(name: str) -> list[str]:
    """A console script this venv provides, or uv as the fallback."""
    found = shutil.which(name)
    return [found] if found else ["uv", "run", name]


def _published(slug: str) -> dict[str, str]:
    """Where a sample's stack answers, and the port it answers on.

    One seed field answers both: `target_url` is the address the flows
    drive — context path included — and its port is the host port the
    stack has to publish for that address to reach the app. Deriving the
    two together is what stops the URL a case is played against from
    drifting away from the port compose binds.
    """
    url = sample(slug)["target_url"]
    port = urlsplit(url).port
    if port is None:
        raise SystemExit(f"sample {slug} target_url has no port: {url}")
    return {"BENCH_BASE_URL": url, "APP_HTTP_PORT": str(port)}


def _eval(
    spec: str,
    args: list[str],
    logs: str,
    env: dict[str, str],
    model: str,
) -> None:
    """One `inspect eval`; `model` is the eval's model.

    It is not what answers a solve's calls: the task builds that model
    itself, from the profile, with the profile's effort and arguments.
    """
    argv = [
        *_tool("inspect"),
        "eval",
        spec,
        *args,
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

    The task resolves the profile itself, from `runs.yaml`; this process
    resolves it too, because only it can hand the provider's credentials
    to `inspect eval` and name the model that answers.
    """
    resolved = settings.profile(profile)
    chosen = load_manifest(manifest_id)
    slug = chosen["sample"]
    workspace = solves.materialise(run, Path(settings.checkout()), pin(slug))
    _build_toolbox(slug, workspace)
    _eval(
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


def score(manifest_id: int, run: str, logs: str) -> None:
    """Grade the tree a solve kept; the scorer starts the stack itself."""
    tree = solves.tree(run)
    if not tree.is_dir():
        raise SystemExit(f"no tree for run {run}: {tree} is missing")
    # What produced this tree, from the run's own record: a re-score of last
    # week's run must not be labelled with today's `.env`.
    record = solves.read(run)
    if "profile" not in record:
        raise SystemExit(
            f"run {run} predates run profiles: its record names no profile, "
            f"so its score cannot be labelled with one; solve it again"
        )
    slug = load_manifest(manifest_id)["sample"]
    env_dir = sample_env(slug)
    credentials = dotenv_values(env_dir / ".env")
    _eval(
        _spec(manifest_id),
        [
            "-T",
            f"manifest_id={manifest_id}",
            "-T",
            "phase=score",
            "-T",
            f"run={run}",
            "-T",
            f"profile={record['profile']}",
            "--max-samples",
            "1",
        ],
        logs,
        {
            **{k: v for k, v in credentials.items() if v is not None},
            **_published(slug),
            "BENCH_CHECKOUT": str(tree),
        },
        settings.SCORE_MODEL,
    )


def capture(manifest_id: int, cases: list[str]) -> None:
    """Freeze a manifest's goldens from its pinned tree.

    `BENCH_CHECKOUT` names the sample's repository here, as it does for
    `task`: the pin is cut from it and only then becomes the tree the
    stack builds. The address the stack publishes — `BENCH_BASE_URL`, and
    the `APP_HTTP_PORT` that serves it — comes from the sample's
    `target_url`, exactly as it does for scoring, because the golden is
    normalized against it.
    """
    chosen = load_manifest(manifest_id)
    slug = chosen["sample"]
    wanted = cases or list(chosen["scope"]["cases"])
    unknown = sorted(set(wanted) - set(chosen["scope"]["cases"]))
    if unknown:
        raise SystemExit(f"manifest {manifest_id} has no case(s): {unknown}")
    commit = pin(slug)
    tree = solves.materialise(
        f"capture-{uuid.uuid4().hex[:8]}",
        Path(settings.checkout()),
        commit,
    )
    # From here the stack must build the pinned tree, not the worktree the
    # pin came from — same env the scorer is given, down to the address it
    # publishes on, because the golden is normalized against that URL.
    os.environ["BENCH_CHECKOUT"] = str(tree)
    os.environ.update(_published(slug))
    credentials = dotenv_values(sample_env(slug) / ".env")
    for key, value in credentials.items():
        if value is not None:
            os.environ[key] = value
    freezing.run(slug, wanted, commit, chosen["bindings"]["db"]["options"])


def _capture_verb(args: argparse.Namespace) -> None:
    capture(args.manifest, args.case)


def _task(args: argparse.Namespace) -> None:
    run = args.run or uuid.uuid4().hex
    print(f"run: {run}", flush=True)
    solve(args.manifest, args.profile, run, args.logs)
    score(args.manifest, run, args.logs)
    print(f"tree: {solves.tree(run)}")


def _score_verb(args: argparse.Namespace) -> None:
    score(args.manifest, args.run, args.logs)


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
        description="Run one manifest: solve it, then score what was left.",
    )
    verbs = parser.add_subparsers(required=True)

    task = verbs.add_parser("task", help="solve and score one manifest")
    task.set_defaults(handler=_task)
    task.add_argument("--manifest", type=int, required=True)
    task.add_argument(
        "--profile",
        required=True,
        help="who solves it: a profile in runs.yaml (agent, model, effort)",
    )
    task.add_argument("--run", help="reuse a run id instead of minting one")
    task.add_argument(
        "--logs", default=str(settings.LOGS), help="Inspect log dir"
    )

    graded = verbs.add_parser("score", help="grade a tree a solve kept")
    graded.set_defaults(handler=_score_verb)
    graded.add_argument("--manifest", type=int, required=True)
    graded.add_argument("--run", required=True)
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
