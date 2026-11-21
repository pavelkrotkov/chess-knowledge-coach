"""Select matching nominal context before applying the public game cap."""

from .opening_fit_reference_counts import MAX_GAMES

CONTEXT = """CASE
    WHEN json_extract(g.context,'$.berserk')='yes' OR json_extract(g.context,'$.rated')=0 THEN 'excluded'
    WHEN :control IS NULL OR json_extract(g.context,'$.TimeControl') IS NULL
      OR json_extract(g.context,'$.rated') IS NULL OR json_extract(g.context,'$.Date')='?'
      OR json_extract(g.context,'$.WhiteElo') IS NULL OR json_extract(g.context,'$.BlackElo') IS NULL THEN 'unknown'
    WHEN json_extract(g.context,'$.TimeControl') != :control THEN 'excluded'
    ELSE 'matched' END"""


def rows(db, parent, move, ply, control):
    values = {
        "control": None if control == "unknown" else control,
        "parent": parent,
        "move": move,
        "ply": ply,
        "limit": MAX_GAMES + 1,
    }
    where = "FROM moves m JOIN games g ON g.id=m.game_id WHERE m.parent=:parent AND m.uci=:move AND m.ply=:ply"
    counts = dict(
        db.execute(
            f"SELECT {CONTEXT} AS category, COUNT(*) {where} GROUP BY category", values
        ).fetchall()
    )
    selected = db.execute(
        f"SELECT g.id,g.total_plies,g.context {where} AND ({CONTEXT})='matched' ORDER BY g.id LIMIT :limit",
        values,
    ).fetchall()
    return selected, {
        "matched_candidates": counts.get("matched", 0),
        "excluded_context": counts.get("excluded", 0),
        "unknown_context": counts.get("unknown", 0),
    }
