"""Check a small number of related fork roots within a cooperative budget."""

import time

from .related_capture_assessment import setup
from .related_fork_assessment import certify

ROWS = 32
PROOFS = 8


def _eligible(item, accept):
    return item["type"] == "corpus" and (accept is None or accept(item))


def search(db, ordered, started, seconds, *, accept=None):
    proofs = 0
    for item in ordered[:ROWS]:
        if time.monotonic() - started >= seconds or proofs >= PROOFS:
            break
        try:
            if not _eligible(item, accept):
                continue
            board, moves, fingerprint = setup(db, item["version"], item["key"])
            if time.monotonic() - started >= seconds:
                break
            proofs += 1
            certify(board, moves, fingerprint)
        except (ValueError, TypeError, KeyError, IndexError):
            continue
        if time.monotonic() - started < seconds:
            return item
        break
    return None
