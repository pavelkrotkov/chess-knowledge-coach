"""Group independently rechecked later-branch observations by move."""

from collections import defaultdict

from .opening_fit_later_source import branch
from .opening_fit_owned_summary import summarize


def group(db, learner, decision, observations, moves):
    grouped, cache = defaultdict(list), {}
    excluded = {"before_decision": 0, "other_branch": 0, "unavailable": 0}
    for item in observations:
        if item["ply"] <= decision["ply"]:
            excluded["before_decision"] += 1
            continue
        try:
            game_id = item["game_id"]
            if game_id not in cache:
                cache[game_id] = branch(db, learner, decision, game_id)
            match = cache[game_id]
            if match is None or match[0] not in moves:
                excluded["other_branch"] += 1
                continue
            move, identity, game = match
            grouped[move].append(
                {
                    "id": identity,
                    "choice": item["choice"],
                    "time_control": game["time_control"],
                    "date": game["projected_start"],
                }
            )
        except (ValueError, TypeError, KeyError, IndexError, StopIteration):
            excluded["unavailable"] += 1
    return {move: summarize(grouped[move]) for move in moves}, excluded
