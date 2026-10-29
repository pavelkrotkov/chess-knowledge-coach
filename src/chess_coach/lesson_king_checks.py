"""Render verified checking replies and king defenses."""

from .lesson_adapter_common import line


def _check_fact(move, check):
    san = check["san"]
    if check["mate"]:
        return f"{san} is immediate checkmate after {move}."
    if check.get("terminal"):
        return f"After {move} {san}, a repetition, draw-claim or terminal boundary prevents further analysis."
    if check.get("king_replies"):
        replies = ", ".join(check["king_replies"])
        return f"Against {san} after {move}, legal king replies include {replies}."
    return f"Against {san} after {move}, no king move is legal; other replies may exist."


def checks_for(fen, label, move, checks):
    facts, lines = [], []
    for check in checks:
        checked = line(fen, f"{label}: legal check", [move, check["san"]])
        if checked:
            lines.append(checked)
            facts.append(_check_fact(move, check))
    return facts, lines
