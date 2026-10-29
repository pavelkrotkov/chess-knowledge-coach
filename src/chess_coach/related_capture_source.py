"""Resolve current subject-owned capture observations and known positions."""

import io

import chess.pgn

from .unified_own_game_evidence import LIMIT, _inspect, _rows
from .unified_own_game_snapshot import snapshot


def source_for_position(db, subject, position):
    for row in _rows(db, subject, position)[:LIMIT]:
        view, review, reasons = _inspect(db, row["id"], subject)
        if (
            not reasons
            and view["outcome"] == "failure"
            and view["objective"]["kind"] == "material_capture"
        ):
            result = snapshot(view, review, row["id"])
            result["opening"] = _opening(db, position)
            return result
    raise ValueError("no current supported capture observation")


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
