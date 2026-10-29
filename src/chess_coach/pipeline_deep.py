"""Run independently bounded selection and deep work after the cheap pipeline."""

from .pipeline_deep_config import public_limits
from .pipeline_deep_cursor import advance, scan
from .pipeline_deep_game import process_game


def process_deep(db, config):
    report = {
        "status": "disabled",
        "examined": 0,
        "selected_games": 0,
        "processed": 0,
        "selected": 0,
        "pending": 0,
        "capped_out": 0,
        "insufficient": 0,
        "unstable": 0,
        "limits": public_limits(config),
        "capped": False,
    }
    key, version, games = scan(db, config)
    if not config.deep_enabled:
        return report
    report["status"] = "complete"
    for row in games[: config.deep_max_scan]:
        if _at_capacity(report, config):
            report["capped"] = True
            break
        game_id = row["id"]
        report["examined"] += 1
        if not process_game(db, game_id, config, report):
            report["status"] = "partial"
            break
        advance(db, key, version, game_id)
    return _finish(report, config, games)


def _finish(report, config, games):
    if len(games) > config.deep_max_scan and report["examined"] == config.deep_max_scan:
        report["capped"] = True
    if report["pending"] and report["processed"] >= config.deep_max_jobs:
        report["capped"] = True
    if report["capped"] or report["pending"]:
        report["status"] = "partial"
    return report


def _at_capacity(report, config):
    return (
        report["selected_games"] >= config.deep_max_games
        or report["processed"] >= config.deep_max_jobs
    )
