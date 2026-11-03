"""The judge: a model reads both span trees and rules on the boundary.

Whether a tree shows a decoupling is not a diff: the per-request SQL a
framework runs stays where it was, a backend may read more rows than the
page did, and which requests are in scope is written in prose in the work
order. So a model reads the base, the submission and that work order, and
answers four yes/no criteria in a fixed schema; the verdict is their
conjunction, computed here, never the model's own summary.

The prompt is `judge.md` beside this file. It is the bench's, not the
agent's: the agent never sees it, so it may say what is being checked.
"""

import json
import re
from pathlib import Path

from inspect_ai.model import GenerateConfig, ResponseSchema, get_model
from inspect_ai.util import json_schema
from pydantic import BaseModel

PROMPT = Path(__file__).with_name("judge.md")
SLOTS = re.compile(r"\{(work_order|before|after)\}")
CRITERIA = (
    "browser_contract_kept",
    "boundary_crossed",
    "page_side_clean",
    "writes_preserved",
)


class Verdict(BaseModel):
    in_scope_requests: list[str]
    browser_contract_kept: bool
    boundary_crossed: bool
    page_side_clean: bool
    writes_preserved: bool
    explanation: str


def prompt(work_order: str, before: str, after: str) -> str:
    """The judge's prompt, filled in one pass.

    Not `str.format`: the prompt spells `{n}` and `{slug}` as the trees do,
    and a tree must never be read as a slot.
    """
    values = {"work_order": work_order, "before": before, "after": after}
    return SLOTS.sub(lambda found: values[found.group(1)], PROMPT.read_text())


def _parse(completion: str) -> Verdict:
    """The verdict, from a completion that may wrap its JSON in prose."""
    start = completion.find("{")
    end = completion.rfind("}")
    if start == -1 or end < start:
        raise ValueError(f"the judge answered no JSON: {completion[:400]!r}")
    return Verdict.model_validate(json.loads(completion[start : end + 1]))


async def rule(profile: dict, text: str) -> tuple[Verdict, str]:
    """Ask the score profile's judge; return its verdict and model name.

    A judge that answers no parseable verdict, or still fails after the
    profile's retries, raises: that case was not measured, and an `error`
    is not averaged with a pass.
    """
    model = get_model(
        profile["judge_model"],
        config=GenerateConfig(
            reasoning_effort=profile["reasoning_effort"],
            max_tokens=profile["max_tokens"],
            max_retries=profile["max_retries"],
        ),
        **profile["model_args"],
    )
    output = await model.generate(
        text,
        config=GenerateConfig(
            response_schema=ResponseSchema(
                name="trace_verdict",
                json_schema=json_schema(Verdict),
            )
        ),
    )
    return _parse(output.completion), str(model)
