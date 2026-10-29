"""Describe verified pawn geometry and supported-piece activity."""

from .lesson_adapter_common import valid_square


def _target_facts(target):
    if target.get("kind") not in {"isolated", "backward"}:
        return []
    if target.get("color") not in {"white", "black"} or not valid_square(target.get("square")):
        return []
    return [
        f"The position contains a {target['color']} {target['kind']} pawn on {target['square']}.",
        target["plan"],
        f"Counterplan: {target['counterplan']}",
    ]


def _activity_facts(item):
    square, pawn = item.get("square"), item.get("pawn")
    if not valid_square(square) or not valid_square(pawn):
        return []
    if item.get("color") not in {"white", "black"} or item.get("piece") not in {
        "knight",
        "bishop",
        "rook",
        "queen",
    }:
        return []
    return [
        f"The {item['color']} pawn on {pawn} geometrically supports its {item['piece']} on {square}."
    ]
