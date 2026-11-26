"""A solve is the change an agent made to a pin, addressed by an id.

Scoring is separate from solving on purpose: a solve is expensive and a
score is cheap, so a run can be graded against a manifest more than once —
after a golden is corrected, say — without paying for the agent again.

    out/solves/<run_id>/
        record.json   what ran, on which commit, how it exited
        diff.patch    what the agent changed, as git would commit it
        agent/        the CLI's own session record, when it keeps one

The tree is not kept. `rebuild` cuts the record's commit again, applies
the patch and refuses a result whose digest is not the record's, so the
patch is the whole run. What it holds is what git would commit: every file
the pin tracks, even one its `.gitignore` names, plus the new files no
`.gitignore` names, minus the ones the agent deleted. The build output an
agent leaves in its checkout is not part of the run, and so never reaches
the image a score builds.
"""

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

import settings

# The stack is the bench's, not the tree's, so a pin carries no stack file:
# deleting one here would keep a list of names to maintain and hide a sample
# that was pinned wrong. Preparing the sample is what keeps them out (see
# `prepare-repo-for-dataset`). `.dockerignore` is one too: a legacy project
# that ships one reads as a project somebody containerised. The bench keeps
# its own, as `Containerfile.dockerignore` beside each Containerfile.
STACK_FILE = re.compile(
    r"^(?:(?:docker|container)file(?:\..*)?"
    r"|(?:docker-)?compose(?:[-.].*)?"
    r"|\.dockerignore"
    r"|entrypoint\.sh|bootstrap\.sh|\.env)$",
    re.IGNORECASE,
)

_GIT_OPTIONS = [
    "-c",
    "core.fsmonitor=false",
    "-c",
    "core.hooksPath=/dev/null",
    "-c",
    "core.autocrlf=false",
]


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


def _git(repo: Path, args: list[str], stdin: bytes) -> bytes:
    return subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            *_GIT_OPTIONS,
            "-c",
            "user.name=Developer",
            "-c",
            f"user.email={settings.GIT_AUTHOR_EMAIL}",
            *args,
        ],
        env=_git_environment(),
        input=stdin,
        capture_output=True,
        check=True,
    ).stdout


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


def _unpack(repo: Path, rev: str, dest: Path) -> None:
    archive = _git(repo, ["archive", rev], b"")
    subprocess.run(["tar", "-x", "-C", str(dest)], input=archive, check=True)


def _commit_all(repo: Path, message: str, force: bool) -> None:
    """One commit of the whole tree; `force` tracks ignored files too.

    The baseline forces, because a pin may track a file its own
    `.gitignore` names (openclinica's `datainfo.properties`): left out of
    the index, the agent's edits to it would be left out of the patch.
    """
    _git(repo, ["init", "-q"], b"")
    _git(repo, ["add", "-Af" if force else "-A"], b"")
    _git(repo, ["commit", "-q", "--allow-empty", "-m", message], b"")


def materialise(repo: Path, pin: str) -> Path:
    """Make an isolated, temporary checkout without benchmark identifiers.

    Beside it, `baseline/` is the pin as one commit whose message is the
    pin itself, so `capture` knows which commit its patch applies to.
    """
    root = Path(tempfile.mkdtemp(prefix="application-"))
    root.chmod(0o755)
    tree = root / "workspace"
    baseline = root / "baseline"
    tree.mkdir()
    baseline.mkdir()
    complete = False
    try:
        _unpack(repo, pin, baseline)
        _refuse_stack_files(baseline)
        _commit_all(baseline, pin, True)
        shutil.copytree(
            baseline,
            tree,
            symlinks=True,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git"),
        )
        _commit_all(tree, "Import project source", False)
        complete = True
        return tree
    finally:
        if not complete:
            shutil.rmtree(root)


def location(run_id: str) -> Path:
    return settings.SOLVES / run_id


def _files(root: Path) -> list[str]:
    """Every file under `root`, `.git` aside, relative and sorted."""
    found = []
    for dirpath, dirs, names in os.walk(root):
        base = Path(dirpath)
        if base == root and ".git" in dirs:
            dirs.remove(".git")
        links = [name for name in dirs if (base / name).is_symlink()]
        for name in names + links:
            found.append(str((base / name).relative_to(root)))
    return sorted(found)


def _digest(root: Path, paths: list[str]) -> str:
    """One hash over each path's kind, executable bit and content."""
    whole = hashlib.sha256()
    for rel in sorted(paths):
        path = root / rel
        if path.is_symlink():
            kind, body = "l", os.readlink(path).encode()
        elif path.is_dir():
            # An embedded repository: git records its commit, not files.
            kind, body = "g", b""
        else:
            # The owner's bit, as git reads it for 100755.
            executable = path.stat().st_mode & stat.S_IXUSR
            kind = "x" if executable else "f"
            body = path.read_bytes()
        whole.update(rel.encode() + b"\0" + kind.encode() + b"\0")
        whole.update(hashlib.sha256(body).digest())
    return whole.hexdigest()


def _reconstruct(repo: Path, rev: str, patch: bytes, dest: Path) -> None:
    """`rev` of `repo`, with `patch` applied, at `dest`, without a `.git`.

    `git apply` runs inside a repository on purpose: outside one it
    resolves paths against whatever repository encloses `dest`, and
    rejects a patch that applies cleanly here.
    """
    dest.mkdir(parents=True)
    _unpack(repo, rev, dest)
    if not patch:
        return
    _commit_all(dest, "base", True)
    _git(dest, ["apply", "--binary", "--whitespace=nowarn", "-"], patch)
    shutil.rmtree(dest / ".git")


def capture(
    run_id: str, checkout: Path, baseline: Path, record: dict
) -> Path:
    """Record what the agent changed, and prove the record rebuilds it."""
    target = location(run_id)
    target.mkdir(parents=True, exist_ok=True)
    pin = _git(baseline, ["log", "-1", "--format=%s"], b"").decode().strip()
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
    _git(baseline, ["add", "-A"], b"")
    diff = _git(
        baseline,
        [
            "diff",
            "--cached",
            "--binary",
            "--full-index",
            "--no-ext-diff",
            "--no-textconv",
            "HEAD",
        ],
        b"",
    )
    paths = _git(baseline, ["ls-files", "-z"], b"").decode()
    digest = _digest(baseline, [p for p in paths.split("\0") if p])
    (target / "diff.patch").write_bytes(diff)
    record = dict(
        record,
        run_id=run_id,
        commit_sha=pin,
        tree_sha256=digest,
        diff_bytes=len(diff),
    )
    (target / "record.json").write_text(json.dumps(record, indent=2) + "\n")
    settings.SCRATCH.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="rebuild-", dir=settings.SCRATCH))
    try:
        _reconstruct(baseline, "HEAD", diff, scratch / "tree")
        again = _digest(scratch / "tree", _files(scratch / "tree"))
    except subprocess.CalledProcessError:
        again = None
    finally:
        shutil.rmtree(scratch)
    if again != digest:
        # Nothing may be lost to a patch git cannot replay (an embedded
        # repository, say): keep what the agent left for a person to read.
        shutil.copytree(
            checkout,
            target / "tree",
            symlinks=True,
            ignore=shutil.ignore_patterns(".git"),
        )
        raise RuntimeError(
            f"run {run_id}: diff.patch does not rebuild the tree the agent "
            f"left; it is kept at {target / 'tree'}, unscorable"
        )
    return target


def rebuild(run_id: str, repo: Path) -> Path:
    """The run's tree, cut again from `repo`, under `settings.SCRATCH`.

    The caller removes the returned directory's parent.
    """
    record = read(run_id)
    if "tree_sha256" not in record:
        raise RuntimeError(
            f"run {run_id} predates rebuildable records: it names no "
            "commit and no digest, so its tree cannot be cut again"
        )
    settings.SCRATCH.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix=f"{run_id}-", dir=settings.SCRATCH))
    root.chmod(0o755)
    tree = root / "workspace"
    try:
        _reconstruct(
            repo,
            record["commit_sha"],
            (location(run_id) / "diff.patch").read_bytes(),
            tree,
        )
        if _digest(tree, _files(tree)) != record["tree_sha256"]:
            raise RuntimeError(
                f"run {run_id}: {record['commit_sha']} plus diff.patch is "
                "not the tree the record describes"
            )
    except BaseException:
        shutil.rmtree(root)
        raise
    return tree


def read(run_id: str) -> dict:
    return json.loads((location(run_id) / "record.json").read_text())


def head(checkout: Path) -> str:
    """The commit a tree is based on, for the sample id."""
    return subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
