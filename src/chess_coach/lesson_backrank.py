"""Extract replayable attack and defense branches from a back-rank proof."""

from .lesson_adapter_common import line
from .lesson_backrank_attack import attacks


def _move(value):
    return (value or {}).get("san")


def _defenses(fen, observation):
    result = []
    choices = (observation.get("defense") or {}).get("alternatives") or []
    for choice in choices:
        for mate in choice.get("back_rank") or []:
            result.append(
                line(
                    fen,
                    "Tested choice and back-rank mate",
                    [_move(choice.get("move")), _move(mate.get("move"))],
                )
            )
    return result


def back_rank(evidence, fen):
    observation = evidence["facts"][0]["payload"]
    lines = [entry for entry in _defenses(fen, observation) + attacks(fen, observation) if entry]
    if not lines:
        return [], []
    return ["The bounded proof contains a back-rank mating line."], lines[:3]
