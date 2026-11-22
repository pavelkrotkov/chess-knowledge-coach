"""Keep the additional full-history index within its declared file budget."""

import time

MAX_BYTES = 20_000_000
PAGE_BYTES = 4096


def configure(db, deadline):
    db.execute(f"PRAGMA page_size={PAGE_BYTES}")
    db.execute(f"PRAGMA max_page_count={MAX_BYTES // PAGE_BYTES}")
    db.execute("PRAGMA temp_store=MEMORY")
    db.execute("PRAGMA journal_mode=MEMORY")
    db.execute(
        "CREATE TABLE histories (game_id INTEGER PRIMARY KEY, identity TEXT NOT NULL, moves TEXT NOT NULL)"
    )
    db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
