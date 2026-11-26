"""A gate passes only if every check passes — never an average.

Inspect's own metrics average, which would give half marks to a submission
that decoupled nothing. That is the failure this bench exists to catch, so
the reduction is stated once, here, and every scorer uses it.
"""

from inspect_ai.scorer import Metric, SampleScore, Value, metric


@metric
def all_must_pass() -> Metric:
    def compute(scores: list[SampleScore]) -> Value:
        values = [float(score.score.value) for score in scores]
        return min(values) if values else 0.0

    return compute
