"""Exact version-28 projection objects, used for creation and validation."""

QUOTE = chr(39)
STATEMENTS = {
    "style_game_times": (
        "CREATE TABLE style_game_times (game_id INTEGER PRIMARY KEY REFERENCES games(id) "
        "ON DELETE CASCADE, version TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ("
        f"{QUOTE}current{QUOTE},{QUOTE}unknown_time{QUOTE},{QUOTE}unknown_identity{QUOTE},"
        f"{QUOTE}stale{QUOTE})), started_at TEXT, white_identity TEXT, black_identity TEXT, "
        f"CHECK(status!={QUOTE}current{QUOTE} OR (started_at IS NOT NULL AND "
        "white_identity IS NOT NULL AND black_identity IS NOT NULL)))"
    ),
    "idx_style_time_white": (
        "CREATE INDEX idx_style_time_white ON style_game_times"
        "(status, version, white_identity, started_at DESC, game_id DESC)"
    ),
    "idx_style_time_black": (
        "CREATE INDEX idx_style_time_black ON style_game_times"
        "(status, version, black_identity, started_at DESC, game_id DESC)"
    ),
    "idx_style_time_status": (
        "CREATE INDEX idx_style_time_status ON style_game_times(status,version)"
    ),
    "style_time_insert": (
        "CREATE TRIGGER style_time_insert AFTER INSERT ON games BEGIN INSERT INTO "
        f"style_game_times(game_id,version,status) VALUES (NEW.id,{QUOTE}{QUOTE},"
        f"{QUOTE}stale{QUOTE}); END"
    ),
    "style_time_invalidate": (
        "CREATE TRIGGER style_time_invalidate AFTER UPDATE OF pgn,white,black ON games "
        f"BEGIN UPDATE style_game_times SET version={QUOTE}{QUOTE},status={QUOTE}stale{QUOTE},"
        "started_at=NULL,white_identity=NULL,black_identity=NULL WHERE game_id=NEW.id; END"
    ),
}
