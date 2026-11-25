"""Validate the selected public record from its standard starting position."""

import chess

from .fact_fingerprint import canonical, digest
from .opening_profile_center_moves import advance


def replay(db, record, first, parent, line, budget, *, include_prefix=False):
    rows = db.execute(
        "SELECT ply,parent,uci,san FROM moves WHERE game_id=? AND ply<=? ORDER BY ply",
        (record, first + len(line["moves"]) - 1),
    ).fetchall()
    if len(rows) != first + len(line["moves"]) - 1 or rows[first - 1][1] != parent:
        raise ValueError("public history unavailable")
    moves = advance(chess.Board(), rows, 1, check=budget.check)
    if moves[first - 1 :] != line["moves"]:
        raise ValueError("public continuation differs")
    prefix = moves[: first - 1]
    result = {"ply": first, "prefix_sha256": digest(canonical(prefix))}
    if include_prefix:
        result["prefix"] = prefix
    return result
