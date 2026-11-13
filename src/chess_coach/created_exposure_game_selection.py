"""Select and retain independent games for a frozen exposure profile."""

from .capture_game_trend_scan import _resume
from .created_exposure_game_cache import binding, valid
from .created_exposure_game_profile import current
from .created_exposure_game_profile import select as select_profile
from .protection_game_source import prepare
from .short_mate_trend_cohort import snapshot
from .short_mate_trend_select import select
from .short_mate_trend_store import read


def _profile(db, learner, old, deadline):
    if old:
        try:
            if current(db, learner, old["profile"]):
                return old["profile"]
        except (ValueError, TypeError, KeyError, IndexError, StopIteration):
            pass
    return select_profile(db, learner, deadline)


def without_source(games, profile):
    return [(game, side) for game, side in games if game["id"] != profile["game_id"]]


def _populate(db, learner, games, state, profile, deadline):
    select(
        db,
        learner,
        games,
        state,
        deadline,
        retain_fields=("analysis", "review"),
        prepare_game=prepare,
        exclude_identity=profile["identity"],
    )
    consumed = {str(row[0]) for row in state["checked"]}
    state["retained"] = {
        key: value for key, value in state["retained"].items() if key not in consumed
    }


def selection(db, learner, path, deadline):
    key = binding(db, learner)
    old = read(path, key, validator=valid)
    profile = _profile(db, learner, old, deadline)
    if profile is None:
        return None
    if old and old["profile"] != profile:
        old = None
    games, coverage, frontier, signatures = snapshot(db, learner, old["checked"] if old else ())
    games = without_source(games, profile)
    state = _resume(old, key, frontier, signatures, games)
    state["profile"], state["coverage"] = profile, coverage
    _populate(db, learner, games, state, profile, deadline)
    return state
