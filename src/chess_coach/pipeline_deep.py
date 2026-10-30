"""Run independently bounded selection and deep work after the cheap pipeline."""

import time

from .pipeline_deep_config import public_limits
from .pipeline_deep_cursor import advance, scan
from .pipeline_deep_game import process_game
from .pipeline_deep_limits import at_capacity, finish


def process_deep(db, config, *, deadline=None):
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
        if at_capacity(report, config) or (deadline is not None and time.monotonic() >= deadline):
            report["capped"] = True
            break
        game_id = row["id"]
        report["examined"] += 1
        if not process_game(db, game_id, config, report, deadline=deadline):
            report["status"] = "partial"
            break
        advance(db, key, version, game_id)
    return finish(report, config, games)
