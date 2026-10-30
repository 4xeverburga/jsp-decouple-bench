"""Freezing a case's golden from the pristine pin.

A golden is what `functional_parity` compares a submission against, so it
has to come from the app as pinned, on a database no other case has
touched — never from the tree under test, and never hand-edited. This is
the old `case-capture` step, host-driven for the same reason scoring is:
the stack is a plain compose project and the browser is the host's.

    BENCH_CHECKOUT=../openclinica BENCH_BASE_URL=http://localhost:8092 \\
      uv run python main.py capture --manifest 13

It cuts a tree from the pin, builds the sample's stack from it, runs each
case's flow once, and writes `expect.json` beside the `flow.py` that drove
it. The table specs come from the case's hand-written `case.json`; the
values come from the run, so nothing here decides what "correct" means.

One stack per case, because a golden assumes a pristine database: the case
that ran first would otherwise be part of the second one's baseline.
"""

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import settings

from .scorers.functional_parity import db
from .scorers.functional_parity.cases import contract, drive
from .scorers.functional_parity.delta import delta_table
from .stack import running


def _say(line: str) -> None:
    print(f"[capture] {line.rstrip()}", file=sys.stderr, flush=True)


async def one(slug: str, case: str, commit: str, target: db.Target) -> Path:
    """Freeze one case: its stack, its flow once, its rows before and after."""
    declared = contract(slug, case)["db"]["tables"]
    tables = {spec["name"]: spec for spec in declared}
    names = list(tables)
    _say(f"{case}: starting a stack")
    async with running(slug) as stack:
        before = await db.snapshot(stack, target, names)
        artifacts, shot = await asyncio.to_thread(drive, slug, case)
        after = await db.snapshot(stack, target, names)
    # A capture is by definition a run that "passed": the page it ended on
    # is interesting only when something differs.
    if shot:
        (settings.ROOT / shot).unlink(missing_ok=True)
    golden = {
        "sample": slug,
        "case": case,
        "sample_commit": commit,
        # Provenance, never compared: the scorer reads `db` and `artifacts`
        # only, so two captures of the same pin differ in this line alone.
        "captured_at": datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        ),
        "db": {
            "tables": {
                name: delta_table(
                    before[name],
                    after[name],
                    spec["key_columns"],
                    spec["ignore_columns"],
                )
                for name, spec in tables.items()
            }
        },
        "artifacts": artifacts,
    }
    path = settings.SAMPLES / slug / "cases" / case / "expect.json"
    path.write_text(json.dumps(golden, indent=2) + "\n")
    _say(f"{case}: wrote {path.relative_to(settings.ROOT)}")
    return path


def run(slug: str, cases: list[str], commit: str, options: dict) -> list[Path]:
    """Freeze every named case of one sample, one stack each."""
    target = db.Target.from_options(options)
    written: list[Path] = []
    for case in cases:
        written.append(asyncio.run(one(slug, case, commit, target)))
    return written
