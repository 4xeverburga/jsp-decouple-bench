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
import re
import shutil
import subprocess
from pathlib import Path

import settings

# The stack is the bench's, not the tree's, so a pin carries no stack file:
# deleting one here would keep a list of names to maintain and hide a sample
# that was pinned wrong. Preparing the sample is what keeps them out (see
# `prepare-repo-for-dataset`). `.dockerignore` is deliberately not a stack
# file: the build context is this very tree, so that file is what keeps
# `target/` and `node_modules/` out of it.
STACK_FILE = re.compile(
    r"^(?:(?:docker|container)file(?:\..*)?"
    r"|(?:docker-)?compose(?:[-.].*)?"
    r"|entrypoint\.sh|bootstrap\.sh|\.env)$",
    re.IGNORECASE,
)


# Where the CLI keeps its session database and log, inside the sandbox.
AGENT_STATE = "/root/.local/share/opencode"


def _refuse_stack_files(tree: Path) -> None:
    """A pin that carries the stack is a preparation mistake, not ours."""
    found = [
        path.relative_to(tree)
        for path in sorted(tree.rglob("*"))
        if path.is_file() and STACK_FILE.match(path.name)
    ]
    if found:
        listed = ", ".join(str(path) for path in found)
        raise RuntimeError(
            f"the pin carries stack files ({listed}): the stack is the "
            "bench's, so delete them in the sample repo and re-pin"
        )


def keep_agent(run_id: str, archive: bytes) -> Path:
    """The agent's own record of the run, as it left it.

    Neither the database nor the log survives the container, and they are
    the only place a run's tool calls are written down: the eval log keeps
    the work order and the scores, not what the agent did between them.
    """
    target = location(run_id) / "agent"
    target.mkdir(parents=True, exist_ok=True)
    path = target / "opencode.tar"
    path.write_bytes(archive)
    return path


def materialise(run_id: str, repo: Path, pin: str) -> Path:
    """The pinned tree, as a baseline commit, if it carries no stack file."""
    tree = settings.WORKSPACES / run_id
    if tree.exists():
        shutil.rmtree(tree)
    tree.mkdir(parents=True)
    archive = subprocess.run(
        ["git", "-C", str(repo), "archive", pin],
        capture_output=True,
        check=True,
    ).stdout
    subprocess.run(["tar", "-x", "-C", str(tree)], input=archive, check=True)
    _refuse_stack_files(tree)
    git = ["git", "-C", str(tree), "-c", "user.name=bench"]
    git += ["-c", "user.email=bench@localhost"]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-qm", "baseline"], check=True)
    return tree


def location(run_id: str) -> Path:
    return settings.SOLVES / run_id


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
