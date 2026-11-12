"""Rotate structural targets independently of the fallback cursor."""

from .style_schedule_budget import CURRENT
from .style_schedule_candidates_rank import rank


def choose(key, sequence, candidates):
    games = {}
    for item in candidates:
        games.setdefault(item["game_id"], []).append(item)
    ordered = sorted(games, key=lambda game: rank(key, "structural", game, 0))
    step = sequence // 2
    game = ordered[step % len(ordered)]
    positions = sorted(
        games[game], key=lambda item: rank(key, "structural", game, item["position_id"])
    )
    return positions[(step // len(ordered)) % len(positions)]


# Both parsing and exact replay spend one history unit per stored ply.
def _fits(count):
    budget = CURRENT.get()
    return budget is None or count * 2 <= budget["limit"] - budget["used"]


def firsts(first, structural_first, index, checks, structural, count):
    if _fits(count):
        if first is None and checks:
            first = index
        if structural_first is None and structural:
            structural_first = index
    return first, structural_first
