"""Where a sample's stack and solve workspace are defined.

Both live in the bench, under `src/samples/<sample>/env/`, never in the
sample tree: the agent gets a checkout with no container files in it.
"""

from pathlib import Path

import settings

from .seeds import source as source_record


def sample_env(slug: str) -> Path:
    """A sample's bench-owned stack files: compose, Containerfile, .env."""
    return settings.SAMPLES / slug / "env"


def scoring_compose(slug: str) -> Path:
    """The scoring stack, built from the tree under test."""
    compose = sample_env(slug) / "compose.yaml"
    if not compose.is_file():
        raise FileNotFoundError(f"no scoring stack for {slug!r}: {compose}")
    return compose


def solve_compose(slug: str) -> Path:
    """The workspace a source is solved in: its own folder, never shared."""
    if not source_record(slug).get("solve"):
        raise ValueError(f"source {slug!r} has no solve configuration")
    compose = sample_env(slug) / "solve.yaml"
    if not compose.is_file():
        raise FileNotFoundError(f"no solve workspace for {slug!r}: {compose}")
    return compose
