"""Run the ordinary archive scan and advance its durable cursor."""

from .pipeline_cursor import CursorCommitBusy, save_cursor
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
        if not _save(db, account, game_id, scan_hash):
            return games, _deferred(scan)
    if not _save(db, account, last_scanned, scan_hash):
        return games, _deferred(scan)
    scan["has_more"] |= scan_input(db, config, engine_hash) != scan_hash
    scan["archive_checked"] = True
    return games, scan


def _save(db, account, game_id, scan_hash):
    try:
        save_cursor(db, account, game_id, scan_hash, classify_commit_busy=True)
    except CursorCommitBusy:
        return False
    return True


def _deferred(scan):
    scan.update(
        has_more=True, archive_checked=False, detail="cursor_busy", error_category="sqlite_busy"
    )
    return scan
