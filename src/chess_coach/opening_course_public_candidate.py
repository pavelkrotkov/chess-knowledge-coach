"""Select a distinct verified four-ply public continuation."""

from .fact_fingerprint import canonical, digest
from .opening_profile_center_window import PLIES, validate
from .opening_reference_source import SOURCE_SHA256
from .opening_reference_url import site as valid_site


def candidate(db, game_id, first, parent, move, owned):
    game = db.execute("SELECT site,total_plies FROM games WHERE id=?", (game_id,)).fetchone()
    if game is None:
        return None
    rows = db.execute(
        """SELECT ply,parent,uci,san FROM moves WHERE game_id=? AND ply>=? AND ply<?
        ORDER BY ply LIMIT ?""",
        (game_id, first, first + PLIES, PLIES),
    ).fetchall()
    state, result = validate(rows, first, game[1], parent, move)
    if state != "valid" or result is None:
        return None
    original, _after, moves = result
    if moves[: len(owned)] == owned:
        return None
    site = valid_site(game[0])
    reference = digest(canonical([SOURCE_SHA256, game_id, first, parent, move, moves, site]))
    return {
        "reference": reference,
        "fen": original.fen(),
        "color": "white" if original.turn else "black",
        "moves": moves,
        "san": [row[3] for row in rows],
        "site": site,
    }
