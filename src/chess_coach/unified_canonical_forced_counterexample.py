"""Replay a bounded, nonterminal forced-promotion counterexample."""


def _counterexample_proof(move, result):
    proof = result.get("proof")
    if (
        move.promotion
        or result.get("status") != "incorrect"
        or result.get("reason") != "no_legal_promotion"
        or not isinstance(proof, dict)
        or proof.get("status") != "disproved"
        or proof.get("reason") != "no_legal_promotion"
    ):
        raise ValueError("forced promotion counterexample unavailable")
    return proof


def counterexample(board, move, result):
    proof = _counterexample_proof(move, result)
    board.push(move)
    if board.is_game_over(claim_draw=True):
        raise ValueError("forced promotion counterexample unresolved")
    defense = board.parse_uci(proof.get("reply", ""))
    if defense not in board.legal_moves:
        raise ValueError("forced promotion reply unavailable")
    board.push(defense)
    if board.is_game_over(claim_draw=True) or any(m.promotion for m in board.legal_moves):
        raise ValueError("forced promotion counterexample unresolved")
    return defense.uci()
