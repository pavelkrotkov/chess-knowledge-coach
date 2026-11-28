"""Prepare newly allowed back-rank defenses on both public branches."""

from functools import partial

from .opening_public_created_backrank_coverage import COUNTS, collect
from .opening_public_fork_later import branches
from .opening_public_mate_coverage import coverage, finish, unavailable
from .opening_public_proof_coverage import _selected
from .opening_public_proof_source import MAX_GAMES


def branch(db, binding, move, deadline, *, start):
    if binding["control"] == "unknown":
        return unavailable("nominal_context_unknown")
    found = _selected(db, binding, move, deadline)
    if found is None:
        return unavailable("deadline")
    rows, context = found
    selected = rows[:MAX_GAMES]
    result = coverage(context, selected, len(rows) > MAX_GAMES, binding, kind="created_backrank")
    result.update(dict.fromkeys((*COUNTS, "unfinished_games"), 0))
    result.update(examples=[], counts_scope="returned_game_inspections_including_partial")
    collect(db, selected, binding, move, start, deadline, result)
    return finish(result)


def evaluate(index, identity, start, deadline):
    binding = {**identity, "index_sha256": identity["policy"]["created_backrank"]["index_sha256"]}
    result, sample = branches(index, binding, deadline, brancher=partial(branch, start=start))
    return result, sample, None
