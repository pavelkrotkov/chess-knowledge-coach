"""Select verified early-center choices for one opening context."""

from collections import defaultdict

from .opening_fit_owned_summary import MIN_GAMES, summarize
from .opening_unfamiliar_sample import _first_turn
from .style_purpose_slots import slots
from .style_report import style_report
from .style_time_candidates import verified
from .style_time_query import load_game

GAME_LIMIT = 25


# Avoid the more costly style replay unless enough reserved games could qualify.
def _relevant(db, learner):
    rows, limits = slots(db, learner)
    targeted = [row for row in rows if row.get("early_center_target")]
    requests = [row["request_id"] for row in targeted if row.get("request_id")]
    completed = _completed(db, requests)
    possible = {row["game_id"] for row in targeted if row.get("request_id") in completed}
    coverage = {
        "targeted": len(targeted),
        "completed": len(completed),
        "unchecked": len(targeted) - sum(row.get("request_id") in completed for row in targeted),
        "possible_games": len(possible),
    }
    return coverage, limits


def _completed(db, requests):
    if not requests:
        return set()
    placeholders = ",".join("?" for _ in requests)
    return {
        row[0]
        for row in db.connection.execute(
            f"SELECT id FROM purpose_analysis_requests WHERE status='complete' AND id IN ({placeholders})",
            requests,
        )
    }


def _game(db, learner, observation, parent):
    game = load_game(db.connection, observation["game_id"])
    color = verified(game, learner)
    if color not in ("white", "black"):
        raise ValueError("opening ownership unavailable")
    first = _first_turn(db, learner, game["id"], color)
    if color == "black" and (not parent or first[0] != parent):
        return None
    return color, game


# Recheck standard first turns and ownership before assigning a cohort vote.
def _group(db, learner, observations, parent):
    choices, games = defaultdict(list), {}
    excluded = {"other_parent": 0, "unavailable": 0}
    for item in observations:
        try:
            game_id = item["game_id"]
            if game_id not in games:
                games[game_id] = _game(db, learner, item, parent)
            context = games[game_id]
            if context is None:
                excluded["other_parent"] += 1
                continue
            color, game = context
            choices[color].append(
                {
                    "id": game["id"],
                    "choice": item["choice"],
                    "time_control": game["time_control"],
                    "date": game["projected_start"],
                }
            )
        except (ValueError, TypeError, KeyError, IndexError, StopIteration):
            excluded["unavailable"] += 1
    return {color: summarize(choices[color]) for color in ("white", "black")}, excluded


def collect(db, learner, parent):
    preliminary, limits = _relevant(db, learner)
    if preliminary["possible_games"] < MIN_GAMES:
        return {"status": "insufficient", "preliminary": preliminary, "limits": limits}
    report = style_report(db, learner, max_games=GAME_LIMIT)
    coverage = report["coverage"]
    groups, excluded = _group(db, learner, report["early_center"]["observations"], parent)
    if coverage.get("boundary_tie"):
        for group in groups.values():
            group["positive"] = False
    return {
        "status": "checked",
        "preliminary": preliminary,
        "scope": coverage,
        "coverage": report["early_center"]["coverage"],
        "colors": groups,
        "excluded": excluded,
        "limits": limits,
    }
