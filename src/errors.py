"""src/errors.py — the only exception types the CLI knows about."""
from __future__ import annotations


class BenchError(Exception):
    """Base: a normal, reportable failure (exit 2)."""


class PreconditionError(BenchError):
    """The world is not in the state a verb requires (dirty tree, wrong commit)."""


class NotFound(BenchError):
    """A row, a case, a manifest or a gate does not exist."""


class UnknownAdapter(BenchError):
    """A manifest binds an adapter the registry cannot resolve."""


class CaseError(BenchError):
    """A behaviour case is malformed or its flow raised."""


class GateError(BenchError):
    """A gate could not measure at all (stack down, DB unreachable)."""
