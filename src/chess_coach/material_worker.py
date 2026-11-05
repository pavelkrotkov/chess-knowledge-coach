"""Process bounded learner material observations without rerunning analysis."""

from collections import Counter

from .material_recent_state import WINDOW
from .material_worker_schedule import run
from .pipeline_inputs import engine_identity


def _recent_report():
    return {
        "examined": 0,
        "games_examined": 0,
        "game_window": WINDOW,
        "scan_limit": None,
        "decision_limit": None,
        "processed": 0,
        "replayed": 0,
        "observed": 0,
        "no_opportunity": 0,
        "unavailable": 0,
        "source_unavailable": 0,
        "pending": None,
        "status": "not_scanned",
    }


def _recent_status(recent):
    if recent["pending"] is None:
        return "not_scanned"
    if recent["unavailable"] or recent["source_unavailable"]:
        return "unavailable"
    return "pending" if recent["pending"] else "complete"


def process_material(db, config, engine_hash=None):
    report = {
        "status": "disabled",
        "examined": 0,
        "processed": 0,
        "replayed": 0,
        "unavailable": 0,
        "capped": False,
        "outcomes": {},
        "recent": _recent_report(),
        "limits": {
            "positions": config.material_max_scan,
            "decisions": config.material_max_decisions,
        },
    }
    if not config.material_enabled:
        return report
    report["status"] = "complete"
    outcomes = Counter()
    engine_hash = engine_hash if engine_hash is not None else engine_identity(config.engine_path)
    run(db, config, engine_hash, report, outcomes)
    if report["capped"] or report["unavailable"]:
        report["status"] = "partial"
    report["recent"]["status"] = _recent_status(report["recent"])
    report["outcomes"] = dict(sorted(outcomes.items()))
    return report
