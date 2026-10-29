"""Present checked pawn geometry, plans and legal recorded continuations."""

from .lesson_adapter_common import line, valid_square
from .lesson_structure_facts import _activity_facts, _target_facts


def _captures(role, value, checked):
    if not checked:
        return []
    result = []
    for capture in value.get("captures", []):
        square, ply, gain = capture.get("square"), capture.get("ply"), capture.get("exchange_gain")
        if (
            valid_square(square)
            and isinstance(ply, int)
            and 0 < ply <= len(checked["moves"])
            and isinstance(gain, int)
        ):
            result.append(
                f"In the recorded {role} line, the pawn on {square} is captured at line ply {ply}; the bounded target-square exchange gains {gain} material units for the capturing side."
            )
    return result


def structure(evidence, fen):
    payload = evidence["facts"][0]["payload"]
    facts = []
    for target in payload.get("targets", []):
        facts.extend(_target_facts(target))
    for item in payload.get("activity", []):
        facts.extend(_activity_facts(item))
    lines = []
    for role, value in (payload.get("lines") or {}).items():
        if role in {"best", "played"} and value:
            checked = line(fen, f"Recorded {role}-search continuation", value.get("san"))
            lines.append(checked)
            facts.extend(_captures(role, value, checked))
    return facts, lines
