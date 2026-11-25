"""Compare only qualified weakness with its stated uncertainty."""

THRESHOLD = 0.6


def _weak(value):
    return value["state"] == "sufficient" and value["mastery"] < THRESHOLD


def winner(capture, fork):
    if capture["state"] != "sufficient" or fork["state"] != "sufficient":
        return _single(capture, fork)
    return _both(capture, fork)


def _single(capture, fork):
    if _weak(capture):
        return "capture"
    if _weak(fork):
        return "fork"
    return "rotate"


def _both(capture, fork):
    delta = capture["mastery"] - fork["mastery"]
    if abs(delta) <= max(capture["uncertainty"], fork["uncertainty"]):
        return "rotate"
    if delta < 0 and _weak(capture):
        return "capture"
    if delta > 0 and _weak(fork):
        return "fork"
    return "rotate"
