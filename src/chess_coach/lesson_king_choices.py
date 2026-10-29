"""Explain checked legal replies after a candidate move."""

from .lesson_adapter_common import line
from .lesson_king_checks import checks_for


def choice(value, label, fen):
    if not value or value.get("status") != "complete":
        return [], []
    move = value["move"]["san"]
    checks = value["checks"]
    facts = [f"After {move}, the opponent has {len(checks)} immediate legal checking moves."]
    actions = [name for name in ("check", "capture", "promotion") if value["move"].get(name)]
    if actions:
        summary = ", ".join(actions)
        facts.append(
            f"The legal move {move} also gives: {summary}. Its compensation is unresolved."
        )
    check_facts, lines = checks_for(fen, label, move, checks)
    facts.extend(check_facts)
    for field in ("captures", "promotions"):
        if value[field]:
            moves = ", ".join(value[field])
            facts.append(f"After {move}, legal opposing {field} include {moves}.")
    _witness(value, move, label, fen, facts, lines)
    return facts, lines


def _witness(value, move, label, fen, facts, lines):
    witness = value.get("reply_witness")
    if witness and witness["status"] == "complete":
        reply = witness["reply"]["san"]
        escapes = ", ".join(witness["king_moves"]) or "none"
        facts.append(
            f"If the opponent replies {reply} after {move}, legal king moves are {escapes}; other replies are possible."
        )
        checked = line(fen, f"{label}: one possible reply", [move, reply])
        if checked:
            lines.append(checked)
