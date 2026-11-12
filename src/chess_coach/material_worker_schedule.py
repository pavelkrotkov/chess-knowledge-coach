"""Share material scan and decision budgets between recent and archive work."""

from .material_fresh import work as fresh_work
from .material_fresh_turn import claim as claim_fresh
from .material_recent_cursor import claim, load
from .material_recent_work import work as recent_work
from .material_worker_archive import work as archive_work


def _recent(db, config, engine_hash, report, outcomes, state, single):
    if single:
        state = claim(db, config.learner, state, next_recent=False)
    scans = min(20, config.material_max_scan if single else config.material_max_scan - 1)
    decisions = min(
        5, config.material_max_decisions if single else config.material_max_decisions - 1
    )
    report["recent"]["scan_limit"] = scans
    report["recent"]["decision_limit"] = decisions
    fresh, fresh_state = claim_fresh(db, config.learner)
    if fresh:
        used = fresh_work(
            db,
            config,
            engine_hash,
            report,
            outcomes,
            report["recent"],
            scans,
            decisions,
            fresh_state,
        )
        return state, used
    return recent_work(
        db, config, engine_hash, state, report, outcomes, report["recent"], scans, decisions
    )


def run(db, config, engine_hash, report, outcomes):
    state = load(db, config.learner)
    single = config.material_max_scan == 1 or config.material_max_decisions == 1
    used = set()
    if not single or state["next_recent"]:
        state, used = _recent(db, config, engine_hash, report, outcomes, state, single)
    if (
        report["examined"] < config.material_max_scan
        and report["processed"] < config.material_max_decisions
    ):
        if single:
            state = claim(db, config.learner, state, next_recent=True)
        archive_work(db, config, report, outcomes, used)
