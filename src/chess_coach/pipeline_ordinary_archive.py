"""Run the ordinary archive scan and advance its durable cursor."""

from .pipeline_cursor import save_cursor
from .pipeline_game import process_game
from .pipeline_inputs import scan_input
from .pipeline_pending import pending_games
from .pipeline_recent_turn import claim


def process_archive(db, config, engine_hash, exclude, *, single):
    if single:
        claim(db, config.learner, next_recent=True)
    pending, scan, cursor = pending_games(db, config, engine_hash, exclude=exclude)
    account, last_scanned, scan_hash = cursor
    games = []
    for game_id, game_hash in pending:
        games.append(process_game(db, game_id, game_hash, config, engine_hash))
        save_cursor(db, account, game_id, scan_hash)
    save_cursor(db, account, last_scanned, scan_hash)
    scan["has_more"] |= scan_input(db, config, engine_hash) != scan_hash
    scan["archive_checked"] = True
    return games, scan
