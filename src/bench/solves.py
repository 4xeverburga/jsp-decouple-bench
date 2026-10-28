"""A solve is the tree an agent left behind, addressed by an id.

Scoring is separate from solving on purpose: a solve is expensive and a
score is cheap, so a tree can be graded against a manifest more than once —
after a golden is corrected, say — without paying for the agent again.

    out/solves/<run_id>/
        record.json   what ran, how it exited, when
        diff.patch    what the agent changed, read from git
        tree/         the checkout it left, for the stack to build
"""

import json
import shutil
import subprocess
from pathlib import Path

from .settings import ROOT

SOLVES = ROOT / "out" / "solves"


def location(run_id: str) -> Path:
    return SOLVES / run_id


def capture(run_id: str, checkout: Path, record: dict) -> Path:
    """Copy the tree aside and record what produced it."""
    target = location(run_id)
    tree = target / "tree"
    target.mkdir(parents=True, exist_ok=True)
    if tree.exists():
        shutil.rmtree(tree)
    shutil.copytree(checkout, tree, symlinks=True)
    # Intent-to-add first: a plain `git diff` drops new files, which is most
    # of what an agent writes.
    subprocess.run(
        ["git", "-C", str(checkout), "add", "-N", "."],
        capture_output=True,
    )
    diff = subprocess.run(
        ["git", "-C", str(checkout), "diff", "--binary"],
        capture_output=True,
    ).stdout
    subprocess.run(
        ["git", "-C", str(checkout), "reset", "-q"], capture_output=True
    )
    (target / "diff.patch").write_bytes(diff)
    record = dict(record, run_id=run_id, diff_bytes=len(diff))
    (target / "record.json").write_text(json.dumps(record, indent=2) + "\n")
    return target


def read(run_id: str) -> dict:
    return json.loads((location(run_id) / "record.json").read_text())


def tree(run_id: str) -> Path:
    return location(run_id) / "tree"


def head(checkout: Path) -> str:
    """The commit a tree is based on, for the sample id."""
    return subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
