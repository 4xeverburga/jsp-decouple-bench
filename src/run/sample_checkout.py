"""src/run/sample_checkout.py — this run's checkout, and nothing else.

`SAMPLE_SANDBOX` is the folder allocated to **one** run. The bench puts the
single checkout of that run in it: nothing is ever cloned next to it, so
nothing can be learned by reading around the tree the agent was given. A
sandbox that already holds anything is refused rather than merged into.

The pin itself is not taken from a working copy on disk. The bench keeps a
bare mirror per sample under `<out>/cache/<slug>.git`, fetched from
`SAMPLE.source` when it lacks the pin, and clones out of that mirror. So a
run needs no network and no credentials, and no other sample's history is
anywhere near the sandbox.

After the clone the repository is scrubbed to a detached HEAD: no remote,
no branches, no tags, no reflog, and no ancestry. The clone is one commit
deep, so the parent objects were never downloaded either — deleting refs
alone would have removed only the *names*, leaving `HEAD`'s history fully
walkable. What survives is the files, and a `.git` that knows one commit.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from src.errors import PreconditionError


@dataclass(frozen=True)
class SamplePin:
    """What the registry knows about the commit a run must work from."""

    slug: str
    source: str
    branch: str
    commit_sha: str
    entrypoint: str | None


def _git_proc(location: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(location), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _git(location: Path, *args: str) -> str:
    proc = _git_proc(location, *args)
    if proc.returncode != 0:
        raise PreconditionError(
            f"git {' '.join(args)} failed in {location}: {proc.stderr.strip()}"
        )
    return proc.stdout.strip()


def _git_outside_repo(*args: str) -> str:
    """`git` that is not pointed at a repository (`clone` has no `-C`)."""
    proc = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise PreconditionError(
            f"git {' '.join(args)} failed: {proc.stderr.strip()}"
        )
    return proc.stdout.strip()


def provision(
    pin: SamplePin,
    sandbox: Path,
    env_file: str,
    cache_dir: Path,
) -> dict:
    """Put the pin in `sandbox`: the folder this one run owns.

    `sandbox` must be absent or empty — one run, one checkout, no siblings
    to read. The commit comes from the local mirror of `pin.source`, and
    the result is a clean worktree detached at `pin.commit_sha` with no
    refs, no remote and the declared `entrypoint` in place.
    """
    sandbox = Path(sandbox).expanduser().resolve()
    cache_dir = Path(cache_dir).expanduser().resolve()

    if sandbox.exists():
        if not sandbox.is_dir():
            raise PreconditionError(
                f"sample sandbox is not a directory: {sandbox}"
            )
        if any(sandbox.iterdir()):
            raise PreconditionError(
                f"sample sandbox must be an empty folder — it holds this "
                f"run's only checkout, and nothing else may sit beside it "
                f"({sandbox})"
            )
    else:
        sandbox.mkdir(parents=True)

    mirror = _mirror(pin, cache_dir)

    # `--depth 1` is what makes the scrub below real. A full clone carries
    # the sample's entire object database, and a commit object names its
    # parent, so removing refs would leave the ancestry walkable.
    # `--no-local` because git ignores `--depth` for a local source
    # otherwise, and `--branch` because a shallow clone needs a ref to cut
    # at: the pin is expected to be that branch's tip.
    _git_outside_repo(
        "clone",
        "--no-local",
        "--depth",
        "1",
        "--branch",
        pin.branch,
        "--no-checkout",
        "--quiet",
        str(mirror),
        str(sandbox),
    )
    has_pin = (
        _git_proc(
            sandbox, "cat-file", "-e", pin.commit_sha + "^{commit}"
        ).returncode
        == 0
    )
    if not has_pin:
        raise PreconditionError(
            f"pin {pin.commit_sha[:10]} is not the tip of '{pin.branch}' in "
            f"{pin.source}. A run clones one commit, so the pin has to be "
            "that branch's tip: push a branch that points at it, then "
            "`make db-init`."
        )

    _git(sandbox, "checkout", "--detach", "--quiet", pin.commit_sha)
    _scrub(sandbox)
    _verify(sandbox, pin.commit_sha)

    if env_file and not (sandbox / env_file).is_file():
        raise PreconditionError(
            f"the pin does not carry '{env_file}'. Credentials come from "
            f"the sample's own committed file (AGENTS rule 6); commit it "
            f"at the pin rather than copying it into a run."
        )

    if pin.entrypoint and not (sandbox / pin.entrypoint).is_file():
        raise PreconditionError(
            f"pinned commit does not contain the declared entrypoint "
            f"'{pin.entrypoint}' (looked in {sandbox}). Point "
            f"`sample.commit_sha` in seeds/samples.json at a commit that "
            f"includes it, then `make db-init`."
        )

    return {
        "location": str(sandbox),
        "source": pin.source,
        "mirror": str(mirror),
        "commit": pin.commit_sha,
        "clean": True,
        "refs": 0,
        "entrypoint": pin.entrypoint,
    }


def _mirror(pin: SamplePin, cache_dir: Path) -> Path:
    """The bare mirror of `pin.source` that is guaranteed to have the pin.

    Built on demand from the registry's source, and only fetched again when
    it does not already contain the commit — so a run in steady state never
    touches the network.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    mirror = cache_dir / f"{pin.slug}.git"
    wants = pin.commit_sha + "^{commit}"

    if not mirror.exists():
        _git_outside_repo(
            "clone", "--bare", "--quiet", pin.source, str(mirror)
        )
        _git(mirror, "config", "remote.origin.url", pin.source)

    if _git_proc(mirror, "cat-file", "-e", wants).returncode != 0:
        _git(
            mirror,
            "fetch",
            "--quiet",
            "--prune",
            "--tags",
            pin.source,
            "+refs/heads/*:refs/heads/*",
            "+refs/tags/*:refs/tags/*",
        )

    if _git_proc(mirror, "cat-file", "-e", wants).returncode != 0:
        raise PreconditionError(
            f"the mirror {mirror} has no commit {pin.commit_sha[:10]} after "
            f"fetching {pin.source}. Push the pin there, or seed the mirror "
            f"by hand: git clone --bare <checkout> {mirror}"
        )
    return mirror


def _scrub(destination: Path) -> None:
    """Leave the clone knowing the commit, and nothing about its past."""
    refs = _git(
        destination, "for-each-ref", "--format=%(refname)"
    ).splitlines()
    for ref in [r for r in refs if r]:
        _git(destination, "update-ref", "-d", ref)
    _git(destination, "remote", "remove", "origin")
    _git(destination, "reflog", "expire", "--expire=now", "--all")
    _git(destination, "gc", "--prune=now", "--quiet")


def _verify(destination: Path, commit_sha: str) -> None:
    """Clean, pinned and anonymous — or the provisioning is wrong."""
    head = _git(destination, "rev-parse", "HEAD")
    if head != commit_sha:
        raise PreconditionError(
            f"provisioned checkout is at {head}, expected {commit_sha}"
        )

    refs = [
        line
        for line in _git(
            destination, "for-each-ref", "--format=%(refname)"
        ).splitlines()
        if line
    ]
    if refs:
        raise PreconditionError(
            f"provisioned checkout still carries refs: {refs[:5]}"
        )

    remotes = _git_proc(
        destination, "config", "--get-regexp", r"^remote\."
    ).stdout.strip()
    if remotes:
        raise PreconditionError(
            f"provisioned checkout still names a remote: {remotes}"
        )

    # A detached HEAD still has parents. Without these two assertions the
    # scrub looks clean while `git log` walks the sample's whole history.
    if _git(destination, "rev-parse", "--is-shallow-repository") != "true":
        raise PreconditionError(
            "provisioned checkout is not shallow: it carries the sample's "
            "history and its parent commits can be read"
        )
    commits = _git(destination, "rev-list", "--count", "HEAD")
    if commits != "1":
        raise PreconditionError(
            f"provisioned checkout reaches {commits} commits, expected 1"
        )

    dirty = [
        line
        for line in _git(destination, "status", "--porcelain").splitlines()
        if line
    ]
    if dirty:
        raise PreconditionError(
            f"provisioned checkout is not clean: {dirty[:5]}"
        )


def show_file(location: Path, commit_sha: str, path: str) -> str:
    """The text of `path` as committed at `commit_sha`.

    Reads the object database, never the worktree: the pinned commit is
    the sample's contract, and the worktree is the agent's work.
    """
    location = Path(location).expanduser().resolve()
    return _git(location, "show", f"{commit_sha}:{path}")


def diff(location: Path, base_commit: str) -> str:
    """Worktree diff against the pin (empty if the agent changed nothing).

    Files the agent created are part of what the agent did, but `git diff`
    ignores them until they are in the index. Mark them intent-to-add so
    the patch carries new files too, then restore the index so the worktree
    is left exactly as it was found.

    Legacy sources are not always valid UTF-8, and `--binary` splices raw
    bytes in, so the patch is decoded lossily: it is an audit artifact, not
    something to feed back into git.
    """
    location = Path(location).expanduser().resolve()
    untracked = _untracked_paths(location)
    if untracked:
        _git(location, "add", "--intent-to-add", "--", *untracked)
    try:
        proc = subprocess.run(
            [
                "git",
                "-C",
                str(location),
                "diff",
                "--binary",
                base_commit,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    finally:
        if untracked:
            _git(location, "reset", "--quiet", "--", *untracked)
    if proc.returncode != 0:
        raise PreconditionError(f"git diff failed: {proc.stderr.strip()}")
    return proc.stdout


def _untracked_paths(location: Path) -> list[str]:
    """Paths git reports as untracked (empty when the tree is clean)."""
    listing = subprocess.run(
        ["git", "-C", str(location), "status", "--porcelain", "-z"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if listing.returncode != 0:
        raise PreconditionError(f"git status failed: {listing.stderr.strip()}")
    return [
        entry[3:]
        for entry in listing.stdout.split("\0")
        if entry.startswith("?? ")
    ]
