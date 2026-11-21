"""Explicit standalone, one-decision public mate policy; adaptive enrollment is closed."""

from .puzzle_session_validate import legal_move

OBJECTIVE = "public_mate_in_one_standalone_v1"
BINDING = {
    "version": OBJECTIVE,
    "verifier": "public-mate-legal-v1",
    "source_kind": "external_public",
    "history": "standalone_fresh",
}


def validate(fen, board, lines, objective):
    if objective != OBJECTIVE:
        return
    _history(fen, board)
    for line in lines:
        moves = line.split()
        if len(moves) != 1:
            raise ValueError("immediate mate requires one move")
        candidate = board.copy()
        candidate.push(legal_move(candidate, moves[0]))
        if not candidate.is_checkmate():
            raise ValueError("immediate mate example unavailable")


def _history(fen, board):
    fields = fen.split() if isinstance(fen, str) else []
    if len(fields) != 6 or not fields[5].isdigit() or int(fields[5]) < 1:
        raise ValueError("standalone mate prompt unavailable")
    if (
        board.halfmove_clock != 0
        or board.fen(en_passant="fen") != board.fen()
        or board.is_game_over(claim_draw=True)
    ):
        raise ValueError("standalone mate prompt unavailable")
