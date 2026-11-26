"""Original-game context shared by related capture selection and backfill."""

import io

import chess.pgn


def baseline(db, source):
    position = source["provenance"]["position_id"]
    row = db.connection.execute(
        "SELECT g.white_elo,g.black_elo FROM positions p JOIN games g ON g.id=p.game_id WHERE p.id=?",
        (position,),
    ).fetchone()
    field = "white_elo" if source["learner_color"] == "white" else "black_elo"
    rating = row[field] if row else None
    return rating if isinstance(rating, int) and 0 < rating < 4000 else None


def _opening(db, position):
    row = db.connection.execute(
        "SELECT g.pgn FROM positions p JOIN games g ON g.id=p.game_id WHERE p.id=?", (position,)
    ).fetchone()
    headers = chess.pgn.read_headers(io.StringIO(row["pgn"])) if row else None
    opening = headers.get("Opening", "") if headers else ""
    return opening.split(":", 1)[0].replace(" ", "_") or None
