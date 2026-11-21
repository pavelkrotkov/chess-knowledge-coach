"""Walk bounded existing profiles and historical analysis records."""

import time

from .analysis_history_identity import Limit, profile
from .analysis_history_inventory_state import row

MAX_ROWS = 100000
SAMPLE_LIMIT = 1024


def _existing(connection, state, native, until):
    if not native:
        return
    for number, stored in enumerate(
        connection.execute(
            "SELECT fingerprint,config_json,nnue,compatibility_json FROM analysis_provenance ORDER BY id"
        )
    ):
        if number >= MAX_ROWS or time.monotonic() >= until:
            raise Limit("inventory limit")
        profile(state, tuple(stored[1:]), expected=stored[0])


def scan(connection, state, until, native, engine_index):
    _existing(connection, state, native, until)
    if native:
        query = """SELECT r.id,r.game_id,r.engine,r.engine_version,r.binary_path,r.binary_version,
            r.created_at,r.config_json,r.nnue,r.compatibility_json,l.run_id IS NOT NULL,
            CASE WHEN l.run_id IS NULL THEN r.config_json ELSE p.config_json END,
            CASE WHEN l.run_id IS NULL THEN r.nnue ELSE p.nnue END,
            CASE WHEN l.run_id IS NULL THEN r.compatibility_json ELSE p.compatibility_json END
            FROM analysis_runs r LEFT JOIN analysis_run_provenance l ON l.run_id=r.id
            LEFT JOIN analysis_provenance p ON p.id=l.provenance_id ORDER BY r.id LIMIT ?"""
    else:
        query = """SELECT id,game_id,engine,engine_version,binary_path,binary_version,created_at,
            config_json,nnue,compatibility_json,0,config_json,nnue,compatibility_json
            FROM analysis_runs ORDER BY id LIMIT ?"""
    seen, sample = set(), set()
    count = 0
    for values in connection.execute(query, (MAX_ROWS + 1,)):
        if count >= MAX_ROWS or time.monotonic() >= until:
            raise Limit("inventory limit")
        key = row(state, values, engine_index=engine_index)
        seen.add(key)
        if count < SAMPLE_LIMIT:
            sample.add(key)
        count += 1
    return count, len(seen), len(sample)
