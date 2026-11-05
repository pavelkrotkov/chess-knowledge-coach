"""Share existing ordinary work budgets between recent and archive games."""

from dataclasses import replace

from .pipeline_ordinary_archive import process_archive
from .pipeline_ordinary_recent import empty_recent
from .pipeline_ordinary_recent import run_recent as execute_recent
from .pipeline_recent_turn import recent_turn


def process_ordinary(db, config, engine_hash):
    single = config.max_games == 1 or config.max_scan == 1
    run_recent = not single or recent_turn(db, config.learner)
    games = []
    recent = empty_recent()
    item = None
    if run_recent:
        item, recent, result = execute_recent(db, config, engine_hash, single=single)
        if result is not None:
            games.append(result)
    scan_limit = config.max_scan - recent["examined"]
    game_limit = config.max_games - len(games)
    if scan_limit and game_limit:
        archive_config = replace(config, max_scan=scan_limit, max_games=game_limit)
        exclude = {item[0]} if item else set()
        archive, scan = process_archive(db, archive_config, engine_hash, exclude, single=single)
        games.extend(archive)
    else:
        scan = {"examined": 0, "limit": 0, "has_more": True, "archive_checked": False}
    return games, scan, recent
