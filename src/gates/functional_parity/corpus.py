"""functional_parity/corpus.py — the case corpus belongs to this gate.

A case *is* a functional-parity test: its contract, its flow and its frozen
golden live together under `cases/`. Nothing outside this package knows
these paths. Other gates consume a case's **result** from the run log
(`out/runs/<run_id>/cases/<case>.json`), never the corpus itself.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.errors import NotFound

ROOT = Path(__file__).resolve().parent / "cases"


def directory(sample: str, case: str) -> Path:
    return ROOT / sample / case


def known(sample: str) -> list[str]:
    return sorted(p.parent.name for p in (ROOT / sample).glob("*/case.json"))


def _path(sample: str, case: str, filename: str, hint: str = "") -> Path:
    path = directory(sample, case) / filename
    if not path.is_file():
        raise NotFound(f"no {filename} for {sample}/{case}{hint}")
    return path


def contract(sample: str, case: str) -> dict[str, Any]:
    return json.loads(_path(sample, case, "case.json").read_text())


def golden(sample: str, case: str) -> dict[str, Any]:
    return json.loads(_path(sample, case, "expect.json",
                            " — run `make case-capture`").read_text())


def flow(sample: str, case: str) -> Path:
    return _path(sample, case, "flow.py")
