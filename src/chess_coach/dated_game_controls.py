"""Compare selected game controls against the original PGN headers."""

import io

import chess.pgn

from .fork_miss_time import distribution


def _headers(rows, check):
    for game in rows:
        check()
        headers = chess.pgn.read_headers(io.StringIO(game["pgn"]))
        check()
        if headers is None or headers.get("TimeControl") != game["time_control"]:
            return False
    return True


def _rows(games, candidates):
    lookup = {game["id"]: game for game, _ in candidates}
    try:
        return [lookup[item["id"]] for item in games[:40]]
    except KeyError:
        return []


def reason(games, candidates, check=lambda: None):
    rows = _rows(games, candidates)
    if len(rows) != 40:
        return "time_control_unknown"
    newer = distribution(game["time_control"] for game in rows[:20])
    earlier = distribution(game["time_control"] for game in rows[20:40])
    if newer is None or earlier is None:
        return "time_control_unknown"
    if not _headers(rows, check):
        return "time_control_source"
    return None if newer == earlier else "time_control_mismatch"
