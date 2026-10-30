"""Reconstruct the original legal threat anchor and defensive choice."""

from .fork_defense_safety import quiet_after


def branch(board, payload):
    if payload["outcome"] == "success":
        anchor = payload["threats"][0]
        anchor_move, proof = anchor["move"], anchor["fork"]
        defense = board.parse_uci(payload["played"]["uci"][0])
    elif payload.get("threat_origin") == "positional_before_played":
        anchor_move, proof = payload["played"]["uci"][0], payload["fork"]
        defense = board.parse_uci(payload["best"]["uci"][0])
    else:
        raise ValueError("created-by-play threat is outside this practice")
    anchored = quiet_after(board, board.parse_uci(anchor_move))
    if anchored is None or defense not in board.legal_moves:
        raise ValueError("fork anchor unavailable")
    return proof, anchored, defense
