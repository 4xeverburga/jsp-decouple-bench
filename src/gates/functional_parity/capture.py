"""functional_parity/capture.py — freeze a case's golden from a pristine app.

Same reset → dump → flow → dump cycle the gate runs, but it writes
`expect.json` and the step screenshots back into the case instead of
comparing them. Only ever runs on a clean checkout at the pinned commit: a
golden captured from modified code is not a golden.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from src.gates.functional_parity import corpus
from src.gates.functional_parity.delta import delta_table
from src.run.atomic import write_json
from src.run.results import utcnow
from src.run.sample_checkout import ensure_pinned


def capture(ctx: Any, case: str, keep_stack: bool = False) -> Path:
    sample = ctx.sample
    preconditions = ensure_pinned(
        ctx.sample_location, sample["commit_sha"], sample.get("entrypoint")
    )

    contract = corpus.contract(sample["slug"], case)
    tables = (contract.get("db") or {}).get("tables") or []
    declared = (contract.get("e2e") or {}).get("artifacts") or []

    stack = ctx.stack()
    try:
        stack.reset()
        database = ctx.adapter("db")
        columns = [t["name"] for t in tables]
        before = database.dump_many(columns)
        artifacts = ctx.adapter("browser").capture_case(
            corpus.flow(sample["slug"], case),
            ctx.base_url(),
            contract.get("e2e") or {},
            ctx.paths.images,
        )
        after = database.dump_many(columns)
    finally:
        if not keep_stack:
            stack.down()

    directory = corpus.directory(sample["slug"], case)
    write_json(
        directory / "expect.json",
        {
            "sample": sample["slug"],
            "case": case,
            "sample_commit": preconditions["commit"],
            "captured_at": utcnow(),
            "db": {
                "tables": {
                    t["name"]: delta_table(
                        before.get(t["name"]) or [],
                        after.get(t["name"]) or [],
                        t.get("key_columns") or ["id"],
                        t.get("ignore_columns") or [],
                    )
                    for t in tables
                }
            },
            "artifacts": {key: artifacts.get(key) for key in declared},
        },
    )
    if ctx.paths.images.is_dir():
        shutil.copytree(
            ctx.paths.images, directory / "images", dirs_exist_ok=True
        )
    return directory / "expect.json"
