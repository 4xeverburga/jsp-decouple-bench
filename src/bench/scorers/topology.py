"""network_isolation as a scorer: the declared topology, read statically.

No container is started: both compose files are rendered and compared, so
the check costs milliseconds and cannot be confused by an app that fails to
boot. The contract is the PIN's file, never the worktree's: an agent that
publishes a port or adds a network must not thereby widen the allowance it
is graded against.

The pin attaches `front` to the database network on purpose — the pristine
app is server-rendered and reads the database directly — so an untouched
tree fails the isolation check, and only real work can pass it.
"""

import asyncio

from inspect_ai.scorer import CORRECT, INCORRECT, Score, Target, scorer
from inspect_ai.solver import TaskState

from ..compose import contract_and_submission, escaped, networks, ports
from ..settings import FRONT_SERVICE
from .metrics import all_must_pass


def checks(slug: str, db_service: str) -> list[dict]:
    contract, current = contract_and_submission(slug)
    allowed = set(contract.get("networks") or {})
    found: list[dict] = []

    for name in sorted(current.get("services") or {}):
        mode = current["services"][name].get("network_mode") or ""
        found.append(
            {
                "case": f"{name}:network_mode",
                "pass": not escaped(mode),
                "detail": mode or "none",
            }
        )

        attached = networks(current, name)
        extra = attached - allowed
        found.append(
            {
                "case": f"{name}:networks",
                "pass": not extra,
                "detail": f"undeclared {sorted(extra)}"
                if extra
                else f"attached {sorted(attached)}",
            }
        )

        undeclared = ports(current, name) - ports(contract, name)
        found.append(
            {
                "case": f"{name}:ports",
                "pass": not undeclared,
                "detail": f"undeclared {sorted(undeclared)}"
                if undeclared
                else f"published {sorted(ports(current, name))}",
            }
        )

    services = current.get("services") or {}
    missing = next(
        (name for name in (FRONT_SERVICE, db_service) if name not in services),
        "",
    )
    shared = networks(current, FRONT_SERVICE) & networks(current, db_service)
    if missing:
        isolation = f"{missing} is missing"
    elif shared:
        isolation = f"shares {sorted(shared)}"
    else:
        isolation = "shares no network"
    found.append(
        {
            "case": f"{FRONT_SERVICE}:isolated_from_{db_service}",
            "pass": not (missing or shared),
            "detail": isolation,
        }
    )

    database = networks(current, db_service)
    widened = database - networks(contract, db_service)
    found.append(
        {
            "case": f"{db_service}:networks_unchanged",
            "pass": not (widened or not database),
            "detail": f"the database joined {sorted(widened)}"
            if widened
            else f"attached {sorted(database)}",
        }
    )
    return found


@scorer(metrics=[all_must_pass()])
def network_isolation(slug: str, db_service: str) -> scorer:
    """One verdict over every shape rule, with the checks kept in metadata."""

    async def score(state: TaskState, target: Target) -> Score:
        found = await asyncio.to_thread(checks, slug, db_service)
        failed = [check for check in found if not check["pass"]]
        passed = len(found) - len(failed)
        return Score(
            value=INCORRECT if failed else CORRECT,
            explanation="; ".join(
                f"{check['case']}="
                f"{'fail' if not check['pass'] else 'pass'} "
                f"({check['detail']})"
                for check in found
            ),
            metadata={
                "checks": {c["case"]: c["pass"] for c in found},
                "value": round(passed / len(found), 4),
            },
        )

    return score
