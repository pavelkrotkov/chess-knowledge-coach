"""Private on-demand mate facts tied to current learner-owned analysis."""

from .mate_inspection_source import checked_board, position_row, source, still_current
from .mate_proof import VERSION, immediate_mates, move_view, prove_short_mates


def inspect_mate(db, position_id, *, learner, expected_fingerprint=None, node_limit=6000):
    position = position_row(db, position_id)
    try:
        snapshot, fingerprint = source(db, position, learner)
        board = checked_board(db, position, snapshot)
    except ValueError:
        return {"status": "unavailable", "version": VERSION}
    if expected_fingerprint is not None and expected_fingerprint != fingerprint:
        return {"status": "stale", "version": VERSION}
    played = board.parse_uci(position["uci"])
    facts = _facts(board, played, node_limit)
    if not still_current(db, position, learner, fingerprint):
        return {"status": "stale", "version": VERSION}
    return {
        **facts,
        "status": "current",
        "version": VERSION,
        "source_fingerprint": fingerprint,
        "analysis_run_id": snapshot["cheap_run_id"],
        "game_id": position["game_id"],
        "position_id": position_id,
        "ply": position["ply"],
        "decision_fen": board.fen(),
        "learner_color": snapshot["color"],
    }


def _facts(board, played, node_limit):
    mates = immediate_mates(board)
    played_view = move_view(board, played)
    board.push(played)
    checkmate, stalemate = board.is_checkmate(), board.is_stalemate()
    board.pop()
    return {
        "played": played_view,
        "immediate_mates": mates,
        "played_checkmate": checkmate,
        "played_stalemate": stalemate,
        "immediate_mate_not_played": bool(mates) and not checkmate,
        "proof": prove_short_mates(board, node_limit=node_limit),
    }
