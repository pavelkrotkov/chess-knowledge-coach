"""Revalidate all back-rank mating witnesses against real history."""

from .back_rank_terminal import terminal
from .mate_practice_lines import prepared_lines


def attacks(board, fact):
    roots = []
    for root in fact["attack"].get("alternatives", []):
        if root["status"] != "proved":
            continue
        defenses = [
            {"defense": witness["defense"], "mate": witness["mate"]["move"]}
            for witness in root["defenses"]
        ]
        roots.append({**root, "defenses": defenses})
    result = prepared_lines(board, {"version": "mate-proof-v1", "alternatives": roots})
    for line in result:
        after = board.copy()
        for move in line.split():
            after.push_uci(move)
        if terminal(after) is None:
            raise ValueError("back-rank mate unavailable")
    return result
