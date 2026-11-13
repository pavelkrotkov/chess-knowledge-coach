"""Probe learner-owned positions through the normalized FEN prefix index."""


def position_probe(db, identity, subject, *, exclude_recognition=None):
    cache = {}

    def contains(key):
        if key not in cache:
            prefix = key + " "
            row = db.connection.execute(
                """SELECT 1 FROM positions p INDEXED BY idx_positions_fen_game
                JOIN games g ON g.id=p.game_id WHERE p.fen>=? AND p.fen<?
                AND (lower(g.white)=? OR lower(g.black)=?) LIMIT 1""",
                (prefix, prefix + "\uffff", identity, identity),
            ).fetchone()
            session = db.connection.execute(
                """SELECT 1 FROM unified_sessions WHERE subject=?
                AND prompt_fen>=? AND prompt_fen<? LIMIT 1""",
                (subject, prefix, prefix + "\uffff"),
            ).fetchone()
            recognition = db.connection.execute(
                """SELECT 1 FROM recognition_attempts WHERE subject=? AND prompt_key=?
                AND attempt_id<>? LIMIT 1""",
                (identity, key, exclude_recognition or ""),
            ).fetchone()
            cache[key] = row is not None or session is not None or recognition is not None
        return cache[key]

    return contains
