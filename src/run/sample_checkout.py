"""src/run/sample_checkout.py — the pinned-checkout precondition.

`SAMPLE_LOCATION` is only *where the sample lives on this filesystem*.
Provenance comes from `SAMPLE.commit_sha`; this module makes the worktree
match it, or refuses to run. It never stashes, resets or force-checks-out.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from src.errors import PreconditionError


def _git(location: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(location), *args],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise PreconditionError(
            f"git {' '.join(args)} failed in {location}: {proc.stderr.strip()}"
        )
    return proc.stdout.strip()


def ensure_pinned(
    location: Path, commit_sha: str, entrypoint: str | None = None
) -> dict:
    location = Path(location).expanduser().resolve()
    if not location.is_dir():
        raise PreconditionError(f"sample location does not exist: {location}")

    try:
        _git(location, "rev-parse", "--git-dir")
    except PreconditionError:
        raise PreconditionError(f"not a git checkout: {location}") from None

    head = _git(location, "rev-parse", "HEAD")
    moved = False
    if head != commit_sha:
        # Safe, non-destructive: no branch moves, the pin is a detached HEAD.
        _git(location, "checkout", "--detach", commit_sha)
        head = _git(location, "rev-parse", "HEAD")
        moved = True

    dirty = [
        line
        for line in _git(location, "status", "--porcelain").splitlines()
        if line
    ]
    if dirty:
        raise PreconditionError(
            "sample worktree is dirty at the pinned commit; refusing to run "
            f"({location}). Commit, revert or clone fresh. "
            f"First entries: {dirty[:5]}"
        )

    if entrypoint and not (location / entrypoint).is_file():
        raise PreconditionError(
            f"pinned commit does not contain the declared entrypoint "
            f"'{entrypoint}' (looked in {location}). Re-pin the sample "
            f"(`make pin`) to a commit that includes it."
        )

    return {
        "location": str(location),
        "commit": head,
        "checked_out": moved,
        "clean": True,
        "entrypoint": entrypoint,
    }


def diff(location: Path, base_commit: str) -> str:
    """Worktree diff against the pin (empty if the agent changed nothing)."""
    location = Path(location).expanduser().resolve()
    proc = subprocess.run(
        ["git", "-C", str(location), "diff", "--binary", base_commit],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise PreconditionError(f"git diff failed: {proc.stderr.strip()}")
    return proc.stdout
