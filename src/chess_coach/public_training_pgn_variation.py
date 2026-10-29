"""Track bounded PGN variation nesting."""


def accept_variation(kind, state):
    if kind == "open":
        if not state["moves"][-1]:
            return False
        state["moves"].append(0)
    else:
        if len(state["moves"]) == 1 or not state["moves"][-1]:
            return False
        state["moves"].pop()
    return True
