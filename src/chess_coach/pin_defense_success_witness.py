"""Find a qualified counterfactual pin witness."""

from .pin_scan import scan


def witness(after):
    if after is None:
        return None
    found = scan(after)
    return found["proven"][0] if found and found["proven"] else None
