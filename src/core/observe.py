"""One run of one case on a stack of its own: what capture and replay share.

A golden is frozen by `capture` and graded by `replay`, and parity on a
no-op run is green only if both observe a case the same way: the same
stack, the same snapshot order, the same flush wait, the same delta. So
both call `observe`, and what differs — where the table specs come from,
what a failed flow means, where the result goes — stays with the caller.
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import settings

from .cases import db
from .cases.cases import FlowAssertionError, drive
from .cases.delta import delta_table
from .stack import running


@dataclass(frozen=True)
class Observation:
    """What one play of a case left: the page, the rows, the spans.

    `failure` and `artifacts` exclude each other: a flow that asserted
    left no artifacts, only the reason and the page it stopped on.
    """

    failure: dict | None
    artifacts: dict | None
    screenshot: str | None
    deltas: dict[str, dict]
    trace: Path | None


async def keep_trace(stack, slug: str, case: str) -> Path | None:
    """Copy the case's spans out: the volume dies with the stack.

    Their only other copy is inside the collector's volume, which
    `down -v` deletes whatever the verdict was. Wait out the export batch
    first, then take the file. None when there is no file: whether that is
    fatal is the reader's call — parity grades behaviour without it,
    `trace_similarity` cannot grade at all, and a capture cannot freeze a
    base.
    """
    target = settings.TRACES / slug / f"{case}-{uuid4().hex[:8]}.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.sleep(settings.TRACE_FLUSH_WAIT_S)
    copied = await asyncio.to_thread(
        stack.copy_out,
        settings.STACK_TRACES_SERVICE,
        settings.STACK_TRACES_FILE,
        target,
    )
    return target if copied else None


async def observe(
    slug: str, case: str, specs: dict[str, dict], target: db.Target
) -> Observation:
    """Play `case` once on a fresh stack; snapshot `specs`' tables around it.

    `specs` maps each table to its `key_columns` and `ignore_columns`. A
    flow that asserts is recorded, not raised: the rows are read either
    way, because when the flow failed the delta is often the better
    evidence. Any other exception is the bench's, and propagates.
    """
    failure = None
    artifacts = None
    shot = None
    async with running(slug, ()) as stack:
        before = await db.snapshot(stack, target, list(specs))
        try:
            artifacts, shot = await asyncio.to_thread(
                drive, slug, case, stack.base_url
            )
        except FlowAssertionError as error:
            failure = {"reason": error.reason, "screenshot": error.screenshot}
            shot = error.screenshot
        after = await db.snapshot(stack, target, list(specs))
        trace = await keep_trace(stack, slug, case)
    return Observation(
        failure=failure,
        artifacts=artifacts,
        screenshot=shot,
        deltas={
            table: delta_table(
                before[table],
                after[table],
                spec["key_columns"],
                spec["ignore_columns"],
            )
            for table, spec in specs.items()
        },
        trace=trace,
    )
