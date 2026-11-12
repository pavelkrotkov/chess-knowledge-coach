"""Choose bounded recent source decisions without engine or outcome scores."""

from .style_schedule_control import select as select_control
from .style_schedule_coverage import summarize_coverage
from .style_schedule_nomination import prioritize
from .style_schedule_scan import read_games
from .style_schedule_target import target as _target
from .style_time_candidates import recent_games

MAX_GAMES = 10


def allocate(db, learner, key, sequence):
    games, coverage = recent_games(db, learner, limit=MAX_GAMES)
    identities = {} if sequence % 4 == 1 else None
    ordered, nominations = prioritize(db, games, sequence, identities=identities)
    candidates, skipped, duplicates, exhausted, reconstructed = read_games(
        db, ordered, 0, identities=identities
    )
    coverage.update(nominations)
    target, structural, unknown = _target(db, key, sequence, candidates)
    coverage["structural_replayed_positions"] = structural
    coverage["structural_replayed_unknown"] = unknown
    coverage["structural_target_selected"] = bool(sequence % 2 == 0 and structural and target)
    control, targeted, nominated = select_control(db, key, sequence, candidates, target)
    coverage["early_center_policy"] = "early-center-v1"
    coverage["early_center_targeted"] = targeted
    coverage["early_center_nominated"] = nominated
    coverage = summarize_coverage(
        db, games, coverage, skipped, duplicates, exhausted, reconstructed
    )
    return coverage, (("target", target), ("control", control)), candidates
