"""The agents the solve phase can run: one row per agent.

The module is named for the table, not for a backend, because the rows are
not all the same kind. Most are CLIs, bridged so that the model that
answers is the eval's whatever name the CLI asks for.

A row is what one agent needs beyond the model that answers: the keyword
that carries the wire model, the prefix it puts in front of that name,
where it keeps its session record, the credential it insists on before it
will start, and the arguments only it takes. Every one of those five
things is a way a CLI varies:

    param   the keyword that carries the wire model. ``opencode`` and
            ``gemini`` name it after themselves, ``claude`` calls it
            ``model_config``; the rest call it ``model``
    prefix  what the CLI puts in front of that name before it asks the
            bridge — ``codex`` serves it as ``inspect/<name>``
    state   where the CLI keeps its session record inside the sandbox
    env     the credential the CLI insists on before it will start
    extra   arguments only that agent takes

The native agent is a row of the same table and the one with no bridge:
its ``param`` is ``None``, so no name is ever asked for and the eval's own
model answers. That ``None`` is the whole difference a caller can see —
there is no branch on the name anywhere.

Only ``opencode`` has been shown to run here end to end. A new CLI agent
must be read before its run is quoted: its version must know the wire name,
and its sandbox must carry the toolchain it expects.
"""

from dataclasses import dataclass
from typing import Any, Callable

from inspect_ai.model import Model
from inspect_swe import claude_code, codex_cli, gemini_cli, opencode

from . import react


@dataclass(frozen=True)
class Agent:
    solver: Callable[..., Any]
    # ``None``: no bridge is asked for a name, the eval's model answers.
    param: str | None
    prefix: str
    state: str | None
    env: dict[str, str]
    extra: dict[str, Any]


AGENTS = {
    "opencode": Agent(
        solver=opencode,
        param="opencode_model",
        prefix="",
        state="/root/.local/share/opencode",
        env={"OPENCODE_API_KEY": "sk-none"},
        extra={},
    ),
    "codex": Agent(
        solver=codex_cli,
        param="model",
        prefix="inspect/",
        state="/root/.codex",
        env={},
        extra={"home_dir": "/root/.codex"},
    ),
    "claude": Agent(
        solver=claude_code,
        # Not ``model``: that one is an Inspect model to serve (it must be
        # ``provider/name``). ``model_config`` is the identity Claude Code
        # presents and asks for, which the alias routes to the answerer.
        param="model_config",
        prefix="",
        state="/root/.claude",
        env={},
        extra={},
    ),
    "gemini": Agent(
        solver=gemini_cli,
        param="gemini_model",
        prefix="",
        state="/root/.gemini",
        env={},
        extra={},
    ),
    # Native: nothing to install, nothing to ask a bridge, no record of its
    # own — its tool calls are in the eval log. Every field but the solver
    # is empty, and saying so row by row is what makes the difference a
    # fact of the table rather than a branch on the name.
    "react": Agent(
        solver=react.solver_for,
        param=None,
        prefix="",
        state=None,
        env={},
        extra={},
    ),
    # The native agent capped at a few messages, for `mockllm/model`: an
    # answerer that never calls `submit()` would otherwise spend the whole
    # solve budget. Only the smoke profile names it.
    "react-mock": Agent(
        solver=react.mock_solver_for,
        param=None,
        prefix="",
        state=None,
        env={},
        extra={},
    ),
}


def state(name: str) -> str | None:
    """Where the agent named ``name`` keeps its session record."""
    return AGENTS[name].state


def aliases(model: Model, wire: str, prefix: str) -> dict[str, Model]:
    """Every spelling of ``wire`` a request for it may carry.

    The bridge declines a name it does not know, and a CLI may drop the
    provider segment or ``#variant`` or add a prefix of its own.
    """
    names = {wire, wire.rsplit("/", 1)[-1]}
    names |= {name.split("#", 1)[0] for name in names}
    spelled = set(names)
    for name in names:
        spelled.add(name if name.startswith(prefix) else prefix + name)
    return {name: model for name in spelled}


def solver_for(
    name: str,
    model: Model,
    wire: str,
    version: str,
    cwd: str,
    compaction: str,
) -> Any:
    """Build the agent named ``name``.

    A CLI is asked for ``wire``: the bridge answers under every spelling
    the CLI may use, and the CLI is installed at ``version`` to run in
    ``cwd``. A native row asks for nothing — there is no bridge and
    nothing to install — so ``model`` alone is passed, which is what its
    solver takes.

    ``compaction`` is the profile's context-window choice. A CLI manages
    its own context, so only ``none`` reaches one: anything else is a
    profile that names a CLI it cannot configure, and is refused here
    rather than silently ignored.
    """
    agent = AGENTS[name]
    if agent.param is None:
        return agent.solver(model=model, compaction=compaction)
    if compaction != "none":
        raise ValueError(
            f"agent {name!r} is a CLI and manages its own context; "
            f"compaction must be 'none', not {compaction!r}"
        )
    return agent.solver(
        cwd=cwd,
        version=version,
        model_aliases=aliases(model, wire, agent.prefix),
        env=agent.env,
        **agent.extra,
        **{agent.param: wire},
    )
