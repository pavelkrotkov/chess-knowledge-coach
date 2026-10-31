"""Match a supplied defense and capture to its candidate pin certificate."""

from .pin_proof import proven
from .related_pin_shape import features


def certified(board, move, line, source):
    for certificate in proven(board, move):
        shape = features(board, move, certificate)
        if not same(shape, source):
            continue
        for branch in certificate["branches"]:
            if (branch["reply"], branch["capture"]) == (line[1], line[2]):
                return shape, certificate, branch
    return None


def same(candidate, source):
    return all(candidate[key] == source[key] for key in ("mover", "target", "geometry"))
