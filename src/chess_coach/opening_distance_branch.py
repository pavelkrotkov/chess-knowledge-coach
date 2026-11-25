"""Replay and compare one source-verified public candidate branch."""

import json

import chess

from .opening_context_replay import replay
from .opening_course_public_candidate import candidate
from .opening_preparation_graph import _branch
from .opening_profile_lookup import MAX_GAMES
from .opening_profile_play import PARENT_PLIES
from .opening_reference_url import site as valid_site


def branch(index, record, first, parent, move, budget):
    line = candidate(index, record, first, parent, move, None)
    if line is None:
        return None
    source = replay(index, record, first, parent, line, budget, include_prefix=True)
    board = chess.Board()
    for uci in source.pop("prefix"):
        budget.check()
        board.push_uci(uci)
    graph = _branch(board, {"uci": " ".join(line["moves"])})
    game = index.execute(
        "SELECT context,site,total_plies FROM games WHERE id=?", (record,)
    ).fetchone()
    return graph, {
        "reference": line["reference"],
        "site": valid_site(game[1]),
        "context": json.loads(game[0]),
        "total_plies": game[2],
        "window_cutoff": game[2] >= first + len(line["moves"]),
        "record_ended": game[2] == first + len(line["moves"]) - 1,
        "source_history": source,
    }


def records(db, parent, move):
    return db.execute(
        "SELECT game_id,MIN(ply) FROM moves WHERE parent=? AND uci=? AND ply<=? "
        "GROUP BY game_id ORDER BY game_id LIMIT ?",
        (parent, move, PARENT_PLIES, MAX_GAMES + 1),
    ).fetchall()
