"""Divide the existing discovery-defense budget between recent and archive."""

from .discovery_defense_archive import work as archive
from .discovery_defense_cursor import load, save
from .discovery_defense_recent import work as recent


def _remaining(report, limits):
    return (
        limits["positions"] - sum(lane["examined"] for lane in report.values()),
        limits["decisions"] - sum(lane["processed"] for lane in report.values()),
    )


def _first_recent(db, config, engine_hash, lanes, attempts, limits, state):
    single = min(limits.values()) == 1
    use_recent = not single or state["next_fresh"]
    if single:
        state = {**state, "next_fresh": not use_recent}
        save(db, config.learner, state)
    used = set()
    if not use_recent:
        return state, single, use_recent, used
    scans = min(10, limits["positions"] if single else limits["positions"] - 1)
    decisions = min(2, limits["decisions"] if single else limits["decisions"] - 1)
    recent(
        db, config, engine_hash, lanes["recent"], attempts["recent"], scans, decisions, state, used
    )
    return state, single, use_recent, used


def run(db, config, engine_hash, lanes, attempts, limits):
    state = load(db, config.learner)
    state, single, use_recent, used = _first_recent(
        db, config, engine_hash, lanes, attempts, limits, state
    )
    scans, decisions = _remaining(lanes, limits)
    if scans and decisions:
        archive(db, config.learner, lanes["archive"], attempts["archive"], scans, decisions, used)
    scans, decisions = _remaining(lanes, limits)
    if single and not use_recent and scans and decisions:
        recent(
            db,
            config,
            engine_hash,
            lanes["recent"],
            attempts["recent"],
            scans,
            decisions,
            state,
            used,
        )
