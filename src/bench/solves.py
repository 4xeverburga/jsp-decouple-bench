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
import os
import re
import shutil
import subprocess
import tempfile
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


def _git_environment() -> dict[str, str]:
    """Keep host Git commands independent of user and inherited Git config."""
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("GIT_")
    }
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return env


# Where the CLI keeps its session database and log is the agent's own
# business: `agents.state(name)` says where, this module only copies it.


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

    Neither the database nor the log survives the container, and for a CLI
    that directory holds more than the transcript does: the eval log
    carries whatever the bridge converted and nothing for what it did not.
    Native ReAct keeps no directory — its trajectory is the log — so this
    is only called for a row that names one.
    """
    target = location(run_id) / "agent"
    target.mkdir(parents=True, exist_ok=True)
    path = target / "session.tar"
    path.write_bytes(archive)
    return path


def materialise(repo: Path, pin: str) -> Path:
    """Make an isolated, temporary checkout without benchmark identifiers."""
    root = Path(tempfile.mkdtemp(prefix="application-"))
    root.chmod(0o755)
    tree = root / "workspace"
    baseline = root / "baseline"
    tree.mkdir()
    baseline.mkdir()
    complete = False
    try:
        archive = subprocess.run(
            ["git", "-C", str(repo), "archive", pin],
            capture_output=True,
            check=True,
        ).stdout
        subprocess.run(
            ["tar", "-x", "-C", str(baseline)],
            input=archive,
            check=True,
        )
        _refuse_stack_files(baseline)
        git_env = _git_environment()
        git = ["git", "-C", str(baseline), "-c", "user.name=Developer"]
        git += ["-c", f"user.email={settings.GIT_AUTHOR_EMAIL}"]
        subprocess.run([*git, "init", "-q"], env=git_env, check=True)
        subprocess.run(
            [
                *git,
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.hooksPath=/dev/null",
                "add",
                "-A",
            ],
            env=git_env,
            check=True,
        )
        subprocess.run(
            [
                *git,
                "-c",
                "core.hooksPath=/dev/null",
                "commit",
                "-qm",
                "Import project source",
            ],
            env=git_env,
            check=True,
        )
        shutil.copytree(
            baseline,
            tree,
            symlinks=True,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git"),
        )
        git = ["git", "-C", str(tree), "-c", "user.name=Developer"]
        git += ["-c", f"user.email={settings.GIT_AUTHOR_EMAIL}"]
        subprocess.run([*git, "init", "-q"], env=git_env, check=True)
        subprocess.run(
            [
                *git,
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.hooksPath=/dev/null",
                "add",
                "-A",
            ],
            env=git_env,
            check=True,
        )
        subprocess.run(
            [
                *git,
                "-c",
                "core.hooksPath=/dev/null",
                "commit",
                "-qm",
                "Import project source",
            ],
            env=git_env,
            check=True,
        )
        complete = True
        return tree
    finally:
        if not complete:
            shutil.rmtree(root)


def location(run_id: str) -> Path:
    return settings.SOLVES / run_id


def capture(
    run_id: str, checkout: Path, baseline: Path, record: dict
) -> Path:
    """Copy the tree aside and record what produced it."""
    target = location(run_id)
    tree = target / "tree"
    target.mkdir(parents=True, exist_ok=True)
    if tree.exists():
        shutil.rmtree(tree)
    shutil.copytree(
        checkout,
        tree,
        symlinks=True,
        ignore=shutil.ignore_patterns(".git"),
    )
    for path in baseline.iterdir():
        if path.name == ".git":
            continue
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    shutil.copytree(
        checkout,
        baseline,
        symlinks=True,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(".git"),
    )
    git_env = _git_environment()
    git = ["git", "-C", str(baseline)]
    subprocess.run(
        [
            *git,
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.hooksPath=/dev/null",
            "add",
            "-N",
            ".",
        ],
        env=git_env,
        check=True,
    )
    diff = subprocess.run(
        [
            *git,
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.hooksPath=/dev/null",
            "diff",
            "--binary",
            "--no-ext-diff",
            "--no-textconv",
        ],
        env=git_env,
        capture_output=True,
        check=True,
    ).stdout
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
