"""The model a score log is labelled with: the one that solved the tree.

A score asks no model of its own except the judge, which builds its own.
Inspect still requires an eval model, and its log viewer lists runs by it,
so the score phase names the solve's `answer_model` instead of a
placeholder. Building that provider for real would need the solve's
credentials in a phase that never calls it; this stand-in only carries the
name, and refuses to answer.
"""

from inspect_ai._util.registry import RegistryInfo, set_registry_info
from inspect_ai.model import GenerateConfig, Model, ModelAPI, ModelOutput


class _Solved(ModelAPI):
    async def generate(self, input, tools, tool_choice, config) -> ModelOutput:
        raise RuntimeError(
            f"{self.model_name} only labels a score; it answers nothing"
        )


def solved_by(answer_model: str) -> Model:
    """A model named exactly `answer_model` that cannot be called.

    A run nothing answered (a no-op, a hand-made tree) records a bare name;
    Inspect needs a provider, so it is listed under `none`, as Inspect's
    own `none/none` is.
    """
    if "/" not in answer_model:
        answer_model = f"none/{answer_model}"
    provider, name = answer_model.split("/", 1)
    # Inspect prints `<registry name>/<model name>`. A subclass per label,
    # never registered, so the real provider of that name stays untouched
    # for the judge.
    api_type = type("Solved", (_Solved,), {})
    set_registry_info(api_type, RegistryInfo(type="modelapi", name=provider))
    api = api_type(
        model_name=name,
        base_url=None,
        api_key=None,
        api_key_vars=[],
        config=GenerateConfig(),
    )
    return Model(api, GenerateConfig())
