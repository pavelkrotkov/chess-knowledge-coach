"""Read only indexed metadata until the game sample has been chosen."""

from .style_time_projection import VERSION


def side_candidates(connection, subject, side, limit):
    return list(
        connection.execute(
            f"""SELECT game_id,started_at FROM style_game_times WHERE status=? AND version=?
        AND {side}_identity=? ORDER BY started_at DESC,game_id DESC LIMIT ?""",
            ("current", VERSION, subject, limit + 1),
        )
    )


def load_game(connection, game_id):
    return connection.execute(
        """SELECT g.*, t.started_at AS projected_start, t.white_identity AS projected_white,
        t.black_identity AS projected_black FROM games g JOIN style_game_times t ON t.game_id=g.id
        WHERE g.id=? AND t.status=? AND t.version=?""",
        (game_id, "current", VERSION),
    ).fetchone()
