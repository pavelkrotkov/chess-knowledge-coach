"""Present concrete, bounded legal choices and replies from a saved observation."""

from .lesson_adapter_common import line
from .lesson_king_choices import choice
from .lesson_king_comparison import comparison


def _geometry(before, after):
    old_pawns = ", ".join(before["pawns"]) or "none"
    new_pawns = ", ".join(after["pawns"]) or "none"
    old_attacks = ", ".join(before["attacked"]) or "none"
    new_attacks = ", ".join(after["attacked"]) or "none"
    old_king, new_king = before["king"], after["king"]
    return (
        f"King zone around {old_king}: shelter pawns {old_pawns}; after the move around {new_king}: {new_pawns}. "
        f"Geometric attacks before: {old_attacks}; after: {new_attacks}. These attacks are not necessarily legal moves."
    )


def king_safety(evidence, fen):
    payload = evidence["facts"][0]["payload"]
    facts = [_geometry(payload["before"], payload["after"])]
    lines = []
    for key, label in (("played", "Played move"), ("alternative", "Legal alternative")):
        choice_facts, choice_lines = choice(payload.get(key), label, fen)
        facts.extend(choice_facts)
        lines.extend(choice_lines)
        if key == "alternative" and payload.get(key):
            san = payload[key]["move"]["san"]
            facts.append(
                f"A legal alternative to examine is {san}; its overall value is unresolved."
            )
    for role, value in payload.get("recorded_lines", {}).items():
        if value:
            checked = line(fen, f"Recorded {role}-search continuation", value.get("san"))
            if checked:
                lines.append(checked)
    facts.extend(comparison(payload))
    coverage = payload["alternative_coverage"]
    examined, total, unresolved = (
        coverage["examined"],
        coverage["legal_count"],
        coverage["unresolved"],
    )
    facts.append(
        f"The comparison examined {examined} of {total} legal alternatives; {unresolved} were unresolved. This selection does not identify the best move."
    )
    facts.append(payload["uncertainty"])
    return facts, lines
