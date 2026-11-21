"""Advance a versioned skewer sample with the existing cohort scheduler."""

from functools import partial

from .capture_game_trend_scan import _resume
from .protection_game_source import prepare
from .protection_game_turns import TURN_SECONDS
from .protection_game_turns import inspect as inspect_turns
from .protection_game_worker import _guarded
from .short_mate_trend_cohort import snapshot
from .short_mate_trend_scan import _inspect
from .short_mate_trend_select import select
from .short_mate_trend_store import read, write
from .skewer_game_proof import inspect
from .skewer_sample_cache import binding, valid


def classify(board, played, deadline, clock):
    proof, reason = inspect(board, played, deadline, clock)
    if clock() >= deadline:
        return "unknown", "deadline"
    if proof is None:
        return "unknown", reason
    return ("played" if proof["played"] else "other"), None


def run(db, learner, path, deadline):
    key = binding(db, learner)
    old = read(path, key, validator=valid)
    games, coverage, frontier, signatures = snapshot(db, learner, old["checked"] if old else ())
    state = _resume(old, key, frontier, signatures, games)
    state["coverage"] = coverage
    select(
        db,
        learner,
        games,
        state,
        deadline,
        retain_fields=("analysis", "review"),
        prepare_game=prepare,
    )
    consumed = {str(row[0]) for row in state["checked"]}
    state["retained"] = {k: v for k, v in state["retained"].items() if k not in consumed}
    if state["selection_complete"]:
        turns = partial(inspect_turns, classifier=classify)
        guarded = partial(_guarded, inspector=turns)
        _inspect(
            db,
            learner,
            state,
            deadline,
            inspector=guarded,
            turn_seconds=TURN_SECONDS,
            recheck_complete=True,
        )
    write(path, state)
