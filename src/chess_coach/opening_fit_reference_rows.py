"""Select a bounded exact public branch with optional nominal-context filtering."""

from .opening_fit_reference_counts import MAX_GAMES


def _rows(db, parent, move, ply):
    return db.execute(
        """SELECT g.id,g.total_plies,g.context FROM moves m JOIN games g ON g.id=m.game_id
        WHERE m.parent=? AND m.uci=? AND m.ply=? ORDER BY g.id LIMIT ?""",
        (parent, move, ply, MAX_GAMES + 1),
    ).fetchall()


def selected(db, parent, move, ply, control, match_context):
    if match_context:
        from .opening_recent_select import rows as selected_rows

        return selected_rows(db, parent, move, ply, control)
    return _rows(db, parent, move, ply), None
