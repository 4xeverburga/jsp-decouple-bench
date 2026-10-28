"""The bench's command line: `python main.py <verb>`.

One manifest takes two `inspect eval` runs — the agent in the workspace
built for it, then the scored tree on the sample's own stack — because a
Task carries exactly one sandbox. What two processes cannot hand each other
is ours, and it is all this file is:

- a run id, which names `out/solves/<id>/`;
- the checkout the scoring phase needs, derived from that id, so a stale
  one cannot quietly grade the previous run's tree;
- the Compose sidecar `sandbox_compose` writes into the tree, removed
  after scoring.

Everything else is Inspect's own CLI (`inspect view`, `inspect log`) or
ruff, and `README.md` shows the two commands by hand.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import uuid
from pathlib import Path

from . import solves
from .seeds import manifest as load_manifest
from .seeds import manifests as all_manifests
from .seeds import source as source_record
from .settings import ROOT

TASKS = ROOT / "main.py"
LOGS = ROOT / "out" / "evals"
MODEL = "mockllm/model"
SANDBOX = ROOT / "src" / "bench" / "compose.solve.yaml"
SIDECAR = ".bench-inspect-compose.yaml"


def _tool(name: str) -> list[str]:
    """A console script this venv provides, or uv as the fallback."""
    found = shutil.which(name)
    return [found] if found else ["uv", "run", name]


def _eval(spec: str, args: list[str], logs: str, env: dict[str, str]) -> None:
    """One `inspect eval`, with the model that is never asked anything.

    The agent is a command inside the sandbox, so no model is in the loop;
    `eval` still requires one, hence the mock.
    """
    argv = [
        *_tool("inspect"),
        "eval",
        spec,
        *args,
        "--model",
        MODEL,
        "--display",
        "plain",
        "--log-dir",
        logs,
    ]
    subprocess.run(argv, cwd=ROOT, env={**os.environ, **env}, check=True)


def _spec(manifest_id: int) -> str:
    """The `@task` this manifest is graded by: its own type, by name."""
    chosen = load_manifest(manifest_id)
    return f"{TASKS.name}@{chosen['task_type']}"


def _sidecar(slug: str, tree: Path) -> Path:
    """Where `sandbox_compose` drops its copy: beside the source's file."""
    compose_file = source_record(slug)["stack"]["compose_file"]
    return (tree / compose_file).with_name(SIDECAR)


def solve(manifest_id: int, agent: str, run: str, logs: str) -> None:
    """Hand the prompt to the agent, in the workspace built for it."""
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
        ],
        logs,
        {"BENCH_SANDBOX": str(SANDBOX)},
    )


def score(manifest_id: int, run: str, logs: str) -> None:
    """Grade the tree a solve kept, on the sample's own stack."""
    tree = solves.tree(run)
    if not tree.is_dir():
        raise SystemExit(f"no tree for run {run}: {tree} is missing")
    chosen = load_manifest(manifest_id)
    sidecar = _sidecar(chosen["source"], tree)
    try:
        _eval(
            _spec(manifest_id),
            [
                "-T",
                f"manifest_id={manifest_id}",
                "-T",
                "phase=score",
                "--max-samples",
                "1",
            ],
            logs,
            {"BENCH_CHECKOUT": str(tree)},
        )
    finally:
        sidecar.unlink(missing_ok=True)


def _task(args: argparse.Namespace) -> None:
    run = args.run or uuid.uuid4().hex
    print(f"run: {run}", flush=True)
    solve(args.manifest, args.agent, run, args.logs)
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
    task.add_argument("--agent", default="true", help="the command it runs")
    task.add_argument("--run", help="reuse a run id instead of minting one")
    task.add_argument("--logs", default=str(LOGS), help="Inspect log dir")

    graded = verbs.add_parser("score", help="grade a tree a solve kept")
    graded.set_defaults(handler=_score_verb)
    graded.add_argument("--manifest", type=int, required=True)
    graded.add_argument("--run", required=True)
    graded.add_argument("--logs", default=str(LOGS), help="Inspect log dir")

    listed = verbs.add_parser("manifests", help="list them and their cases")
    listed.set_defaults(handler=_manifests)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    args.handler(args)
