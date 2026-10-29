"""Probe learner-owned positions through the normalized FEN prefix index."""


def position_probe(db, identity, subject):
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
            cache[key] = row is not None or session is not None
        return cache[key]

    return contains
