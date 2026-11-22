"""Replay a later fork window with the original public move stack."""

from .fact_fingerprint import canonical, digest
from .opening_public_fork_later_history import WINDOW, positions
from .opening_public_fork_scan import scan
from .opening_public_proof_replay import _attribution


def inspect(db, row, binding, move, budget, deadline):
    identity, moves, rows, candidates, censored, safe = positions(db, row, binding, move, deadline)
    if row[1] < binding["ply"] + WINDOW:
        return None, censored
    item = scan(candidates, rows, budget, deadline, safe=safe)
    if item["example"] is not None:
        example = item["example"]
        _attribution(db, row[0], row[2], binding, example)
        example["source_identity"] = identity
        example["full_history_sha256"] = digest(canonical(moves))
    return item, censored
