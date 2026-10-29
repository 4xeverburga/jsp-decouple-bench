"""The CLI agents the solve phase can run.

Each one is a solver in `inspect_swe`, and each is **bridged**: the model
that answers is the eval's, whatever name the CLI asks the bridge for. Six
things differ, and this module is the only place that knows them:

    solver  the solver itself
    param   the keyword that carries the wire model. `opencode` and
            `gemini` name it after themselves; the rest call it `model`
    prefix  what the CLI puts in front of that name before it asks the
            bridge — `codex` serves it as `inspect/<name>`
    state   where the CLI keeps its session record inside the sandbox, so
            a finished run can still be read after the container is gone
    env     the credential the CLI insists on before it will start. The
            bridge accepts anything, so these are dummies
    extra   arguments only that agent takes. `codex` needs its home out of
            the checkout: its default is `<cwd>/.codex`, which would land
            in the agent's own diff

Only `opencode` has been shown to run here end to end. The others are one
entry away, but a run that names a new agent has to be read before it is
quoted: the version in `.env` must be one whose catalogue knows the wire
name, and the sandbox must carry the toolchain the agent expects.
"""

from dataclasses import dataclass
from typing import Any, Callable

from inspect_ai.model import Model
from inspect_swe import claude_code, codex_cli, gemini_cli, opencode


@dataclass(frozen=True)
class Agent:
    solver: Callable[..., Any]
    param: str
    prefix: str
    state: str
    env: dict[str, str]
    extra: dict[str, str]


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
        param="model",
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
}


def state(name: str) -> str:
    """Where the agent named `name` keeps its session record."""
    return AGENTS[name].state


def aliases(model: Model, wire: str, prefix: str) -> dict[str, Model]:
    """Every spelling of `wire` a request for it may carry.

    The bridge declines a name it does not know (`Add ... to
    model_aliases`), and a CLI is free to drop the provider segment or the
    `#variant`, or to add a prefix of its own, so one alias per spelling
    beats guessing which one this version sends.
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
) -> Any:
    """The agent named `name`, asking the bridge for `wire`.

    `model` is what answers: the wire name is only the string the CLI
    formats its requests for, and the alias is what ties the two together.
    """
    agent = AGENTS[name]
    return agent.solver(
        cwd=cwd,
        version=version,
        model_aliases=aliases(model, wire, agent.prefix),
        env=agent.env,
        **agent.extra,
        **{agent.param: wire},
    )
