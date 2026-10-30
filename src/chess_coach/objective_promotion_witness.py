"""Validate every stored defense and its legal promoting reply."""

import chess

from .mate_proof_search import MAX_REPLIES


def choose(board, proof):
    if proof.get("status") != "proved":
        raise ValueError("promotion proof unavailable")
    witnesses = proof.get("witnesses")
    replies = sorted(move.uci() for move in board.legal_moves)
    if not isinstance(witnesses, list) or len(replies) > MAX_REPLIES:
        raise ValueError("promotion proof unavailable")
    if sorted(item.get("reply") for item in witnesses) != replies:
        raise ValueError("promotion defenses changed")
    for item in witnesses:
        _legal_promotion(board, item)
    return min(witnesses, key=lambda item: item["reply"])


def _legal_promotion(board, item):
    child = board.copy(stack=True)
    reply = child.parse_uci(item["reply"])
    if not reply or reply not in child.legal_moves:
        raise ValueError("promotion defense unavailable")
    child.push(reply)
    move = chess.Move.from_uci(item["promotion"])
    if not move.promotion or move not in child.legal_moves:
        raise ValueError("promotion continuation unavailable")
