"""Observe independently qualified back-rank mates in one public history."""

from .opening_public_back_rank_example import certificate, classify
from .opening_public_fork_later_history import positions
from .opening_public_fork_windows import bounds
from .opening_public_mate_coverage import observation
from .opening_public_mate_game import _terminal
from .opening_public_mate_policy import check


def inspect(db, row, binding, branch, start, deadline):
    window = binding["policy"]["back_rank"]["window"]
    source, moves, rows, candidates, censored, safe = positions(
        db, row, binding, branch, deadline, window=window
    )
    if not candidates:
        first, _ = bounds(binding["ply"], row[1], window)
        return {**observation(censored, ended=row[1] < first, incomplete=True), "other_mates": 0}
    if not safe and not _terminal(candidates, moves, row[2], censored):
        raise ValueError("back-rank history unavailable")
    other_mates = 0
    for ply, board, recorded in candidates:
        check(deadline)
        qualified, other = classify(board, deadline)
        other_mates += other
        if qualified:
            value = certificate(
                db,
                row,
                binding,
                source,
                moves,
                rows,
                ply,
                board,
                recorded,
                qualified,
                start,
                deadline,
            )
            return {
                **observation(censored, example=value, analyzed=True),
                "other_mates": other_mates,
            }
    return {**observation(censored, analyzed=True), "other_mates": other_mates}
