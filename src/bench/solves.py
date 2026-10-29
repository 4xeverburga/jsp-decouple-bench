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

import settings

# The stack is the bench's, not the tree's: none of these reach the agent.
# `.dockerignore` is deliberately NOT here: the build context is this very
# tree, so that file is what keeps `target/` and `node_modules/` out of it.
CONTAINER_FILES = (
    "Dockerfile",
    "Containerfile",
    "compose.yaml",
    "compose.yml",
    "docker-compose.yml",
    "docker-compose.yaml",
    "entrypoint.sh",
    "bootstrap.sh",
    ".env",
    ".env.example",
)


# Where the CLI keeps its session database and log, inside the sandbox.
AGENT_STATE = "/root/.local/share/opencode"


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
    """The pinned tree without container files, as a baseline commit."""
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
    for name in CONTAINER_FILES:
        (tree / name).unlink(missing_ok=True)
    # Variants a sample may carry: docker-compose-it.yml, -override, ...
    for variant in tree.glob("docker-compose*"):
        variant.unlink()
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
