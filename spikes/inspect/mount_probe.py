"""Spike: does an Inspect sandbox permit a writable bind of the host tree?

The bench's whole model is "hand the agent a checkout, let it edit in place,
read the diff back from git". Inspect's sandbox docs say writable host
mounts are refused, and only read-only ones are allowed. If that holds, an
Inspect port cannot keep the checkout protocol as it stands.

`SANDBOX_MOUNT_MODE` picks the mount: `rw` (default) or `ro`.
"""

import os

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.scorer import (
    CORRECT,
    INCORRECT,
    Score,
    Target,
    accuracy,
    scorer,
)
from inspect_ai.solver import Generate, TaskState, solver
from inspect_ai.util import (
    ComposeConfig,
    ComposeService,
    SandboxEnvironmentSpec,
    sandbox,
)

CHECKOUT = os.environ["SANDBOX_CHECKOUT"]
MOUNT_MODE = os.environ["SANDBOX_MOUNT_MODE"]


@solver
def touch_checkout():
    """Prove the mount is reachable and writable, or report the failure."""

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        result = await sandbox().exec(
            ["sh", "-c", "ls /checkout | head -3; touch /checkout/.spike"]
        )
        state.metadata["probe"] = (
            f"success={result.success} code={result.returncode} "
            f"out={result.stdout.strip()!r} "
            f"err={result.stderr.strip()[:300]!r}"
        )
        return state

    return solve


@scorer(metrics=[accuracy()])
def wrote_through():
    async def score(state: TaskState, target: Target) -> Score:
        ok = "success=True" in state.metadata.get("probe", "")
        return Score(
            value=CORRECT if ok else INCORRECT,
            answer=state.metadata.get("probe", ""),
            explanation=state.metadata.get("probe", ""),
        )

    return score


@task
def mount_probe():
    suffix = ":ro" if MOUNT_MODE == "ro" else ""
    config = ComposeConfig(
        services={
            "default": ComposeService(
                image="alpine:3.20",
                init=True,
                command="tail -f /dev/null",
                volumes=[f"{CHECKOUT}:/checkout{suffix}"],
            )
        }
    )
    return Task(
        dataset=[Sample(input="probe", target="probe")],
        solver=[touch_checkout()],
        scorer=wrote_through(),
        sandbox=SandboxEnvironmentSpec("docker", config),
    )


@task
def mount_probe_file():
    """Same probe, from compose-rw.yaml, which sets the documented opt-out."""
    return Task(
        dataset=[Sample(input="probe", target="probe")],
        solver=[touch_checkout()],
        scorer=wrote_through(),
        sandbox=("docker", "compose-rw.yaml"),
    )
