"""Swap only the two owned-family positions in the existing quota pass."""


def owned(state, index, source):
    if not _enabled(state, source):
        return source
    winner = state["priority"]["winner"]
    turn = state["family_turn"]
    first = 0 if turn < 2 else 4 - turn
    if index == first:
        return winner
    return "fork" if winner == "capture" else "capture"


def _enabled(state, source):
    if state["v"] != 8 or source not in {"capture", "fork"}:
        return False
    priority = state["priority"]
    return (
        priority is not None
        and priority["winner"] != "rotate"
        and state["priority_goal"] not in {"capture", "fork"}
    )
