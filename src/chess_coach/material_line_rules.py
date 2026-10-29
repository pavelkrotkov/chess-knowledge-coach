"""Validate a short exact engine line and reject unsupported continuation moves."""

MAX_LINE_PLIES = 4


def eligible_moves(line, expected, *, allow_checks=False):
    if not isinstance(line, dict) or line.get("status") != "limited":
        return None
    if not _exact_line(line):
        return None
    raw = line["pv"].split()[: 8 if allow_checks else MAX_LINE_PLIES]
    moves = raw[: len(raw) - len(raw) % 2]
    if len(moves) < 2 or (expected is not None and moves[0] != expected):
        return None
    return moves


def _exact_line(line):
    return (
        line.get("score_kind") == "cp"
        and line.get("score_bound") == "exact"
        and isinstance(line.get("pv"), str)
    )
