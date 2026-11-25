"""Validate the selected public record from its standard starting position."""

import chess

from .fact_fingerprint import canonical, digest
from .opening_storage import position_key


def replay(db, record, first, parent, line, budget):
    rows = db.execute(
        "SELECT ply,parent,uci,san FROM moves WHERE game_id=? AND ply<=? ORDER BY ply",
        (record, first + len(line["moves"]) - 1),
    ).fetchall()
    if len(rows) != first + len(line["moves"]) - 1 or rows[first - 1][1] != parent:
        raise ValueError("public history unavailable")
    board = chess.Board()
    moves = []
    for ply, before, uci, san in rows:
        budget.check()
        if (ply, position_key(board)) != (len(moves) + 1, before):
            raise ValueError("public history differs")
        move = board.parse_uci(uci)
        if move not in board.legal_moves or board.san(move) != san:
            raise ValueError("public history is illegal")
        moves.append(uci)
        board.push(move)
    if moves[first - 1 :] != line["moves"]:
        raise ValueError("public continuation differs")
    return {"ply": first, "prefix_sha256": digest(canonical(moves[: first - 1]))}
