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
import uuid
from pathlib import Path

from dotenv import dotenv_values

import settings

from . import capture as freezing
from . import solves
from .compose import sample_env
from .seeds import manifest as load_manifest
from .seeds import manifests as all_manifests
from .seeds import pin

TASKS = settings.ROOT / "main.py"
EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max")


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
    extra: tuple[str, ...],
) -> None:
    """One `inspect eval`; `model` answers the agent's bridged calls."""
    argv = [
        *_tool("inspect"),
        "eval",
        spec,
        *args,
        "--model",
        model,
        *extra,
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


def solve(
    manifest_id: int,
    model: str,
    agent: str,
    agent_model: str,
    agent_version: str,
    run: str,
    logs: str,
    extra: tuple[str, ...],
) -> None:
    """Let the agent work on a tree cut from the pin, in its own workspace."""
    chosen = load_manifest(manifest_id)
    slug = chosen["source"]
    workspace = solves.materialise(run, Path(settings.checkout()), pin(slug))
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
            f"agent={agent}",
            "-T",
            f"agent_model={agent_model}",
            "-T",
            f"agent_version={agent_version}",
            "-T",
            f"model_target={model}",
        ],
        logs,
        {
            "BENCH_CHECKOUT": str(workspace),
            "BENCH_SAMPLE_ENV": str(sample_env(slug)),
            "SOLVE_ROOT": settings.SOLVE_ROOT,
            **settings.MODEL_ENV,
        },
        model,
        extra,
    )


def score(manifest_id: int, run: str, logs: str) -> None:
    """Grade the tree a solve kept; the scorer starts the stack itself."""
    tree = solves.tree(run)
    if not tree.is_dir():
        raise SystemExit(f"no tree for run {run}: {tree} is missing")
    # What produced this tree, from the run's own record: a re-score of last
    # week's run must not be labelled with today's `.env`.
    record = solves.read(run)
    slug = load_manifest(manifest_id)["source"]
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
            f"agent={record['agent']}",
            "-T",
            f"agent_model={record['agent_model']}",
            "-T",
            f"agent_version={record['agent_version']}",
            "-T",
            f"model_target={settings.SCORE_MODEL}",
            "--max-samples",
            "1",
        ],
        logs,
        {
            **{k: v for k, v in credentials.items() if v is not None},
            "BENCH_CHECKOUT": str(tree),
        },
        settings.SCORE_MODEL,
        (),
    )


def capture(manifest_id: int, cases: list[str]) -> None:
    """Freeze a manifest's goldens from its pinned tree.

    `BENCH_CHECKOUT` names the sample's repository here, as it does for
    `task`: the pin is cut from it and only then becomes the tree the
    stack builds. `BENCH_BASE_URL` is the address the stack will publish,
    exactly as it is for scoring, because the golden is normalized against
    it.
    """
    chosen = load_manifest(manifest_id)
    slug = chosen["source"]
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
    # pin came from — same env the scorer is given.
    os.environ["BENCH_CHECKOUT"] = str(tree)
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
    extra: list[str] = []
    for arg in args.model_arg:
        extra += ["-M", arg]
    if args.reasoning_effort:
        extra += ["--reasoning-effort", args.reasoning_effort]
    solve(
        args.manifest,
        args.model,
        args.agent,
        args.agent_model,
        args.agent_version,
        run,
        args.logs,
        tuple(extra),
    )
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
        "--model",
        default=settings.ANSWER_MODEL,
        help="provider/model that answers the agent; the default is the one "
        "BENCH_ANSWER_MODEL names",
    )
    task.add_argument(
        "--agent",
        default=settings.AGENT,
        help="which CLI agent solves it: a name in src/bench/agents.py",
    )
    task.add_argument(
        "--agent-model",
        default=settings.AGENT_MODEL,
        help="the wire model that agent formats its requests for",
    )
    task.add_argument(
        "--agent-version",
        default=settings.AGENT_VERSION,
        help="the version of that agent to install in the sandbox",
    )
    task.add_argument(
        "--model-arg",
        action="append",
        default=[],
        help="native model argument for --model, repeatable (key=value)",
    )
    task.add_argument(
        "--reasoning-effort",
        choices=EFFORTS,
        help="effort the answering model is asked to spend on reasoning",
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
