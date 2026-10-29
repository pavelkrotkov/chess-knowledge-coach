"""Evaluate game-ending positions and zeroing positions."""


def terminal(board):
    outcome = board.outcome(claim_draw=False)
    if outcome is None:
        return None
    if outcome.winner is None:
        return (0, 0, "automatic_draw")
    return (-1, -1, "checkmate")


def reset_value(board, tablebase):
    try:
        raw = tablebase.probe_wdl(board)
    except (KeyError, OSError, ValueError):
        return (-1, 1, "table_missing")
    value = 1 if raw == 2 else -1 if raw == -2 else 0
    return (value, value, f"wdl:{raw}")
