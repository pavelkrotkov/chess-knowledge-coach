"""Check each target-capture witness with full draw history."""

from .fork_branch import defense_witness


def witness(board, reply, item, color, initial):
    after = board.copy()
    after.push(reply)
    if unclear(after):
        return None
    witness = defense_witness(board, reply, item["slider"], [item["target"]], color, initial)
    if witness is None:
        return None
    after.push_uci(witness["capture"])
    if unclear(after):
        return None
    for response in after.legal_moves:
        child = after.copy()
        child.push(response)
        if unclear(child):
            return None
    return witness


def unclear(board):
    return board.is_game_over(claim_draw=True) or board.is_repetition(2)
