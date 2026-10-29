"""Extract legal branches from bounded back-rank attack proofs."""

from .lesson_adapter_common import line


def _move(value):
    return (value or {}).get("san")


def _immediate(fen, root):
    if root.get("distance_plies") != 1:
        return []
    return [line(fen, "Proved immediate back-rank mate", [_move(root.get("move"))])]


def attacks(fen, observation):
    result = []
    roots = (observation.get("attack") or {}).get("alternatives") or []
    for root in roots:
        if root.get("status") != "proved":
            continue
        result.extend(_immediate(fen, root))
        for branch in root.get("defenses") or []:
            mate = branch.get("mate") or {}
            result.append(
                line(
                    fen,
                    "Proved back-rank attack and reply",
                    [
                        _move(root.get("move")),
                        _move(branch.get("defense")),
                        _move(mate.get("move")),
                    ],
                )
            )
    return result
