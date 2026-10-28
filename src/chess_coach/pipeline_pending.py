"""Select bounded pending games, placing previously failed games behind new work."""

from .db import Database
from .pipeline_config import PipelineConfig
from .pipeline_cursor import has_more, scan_from
from .pipeline_inputs import scan_input
from .pipeline_scan_item import pending_game


def pending_games(db: Database, config: PipelineConfig, engine_hash: str | None):
    scan_hash = scan_input(db, config, engine_hash)
    account, games = scan_from(db, config.learner, config.max_scan, scan_hash)
    pending = []
    scanned = 0
    last_game = 0
    for game in games[: config.max_scan]:
        scanned += 1
        last_game = game["id"]
        try:
            item = pending_game(db, game, config, engine_hash)
        except Exception:
            item = (game["id"], None)
        if item is not None:
            pending.append(item)
        if len(pending) == config.max_games:
            break
    return (
        pending,
        {
            "examined": scanned,
            "limit": config.max_scan,
            "has_more": has_more(db, games, scanned, last_game),
        },
        (account, last_game, scan_hash),
    )
