"""Find a concrete bounded recapture of an immediate front-piece capture."""

from .material_exchange_rules import unclear
from .material_lines import material
from .material_reply_guard import MAX_REPLIES
from .objective_pin_slide_budget import take
from .objective_pin_slide_neutral import neutral


def recapture(board, attack, target):
    if any((board.gives_check(attack), attack.promotion, board.is_en_passant(attack))):
        return None
    color = board.turn
    initial = material(board, color)
    taken = board.copy(stack=True)
    taken.push(attack)
    if unclear(taken) or taken.is_game_over(claim_draw=True):
        return None
    replies = list(taken.legal_moves)
    take(len(replies) + 1)
    if len(replies) > MAX_REPLIES:
        return None
    for reply in sorted(replies, key=lambda move: move.uci()):
        if neutral(taken, reply, target, color, initial):
            return {"capture": attack.uci(), "recapture": reply.uci()}
    return None
