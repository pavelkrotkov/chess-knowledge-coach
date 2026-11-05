"""Find the next bounded indexed slice of recent played-time candidates."""

from .style_time_projection import VERSION


def _side(connection, subject, side, limit, after):
    boundary = "AND (started_at,game_id)<(?,?)" if after else ""
    args = ["current", VERSION, subject]
    if after:
        args.extend(after)
    args.append(limit + 1)
    return list(
        connection.execute(
            f"""SELECT game_id,started_at FROM style_game_times
            WHERE status=? AND version=? AND {side}_identity=? {boundary}
            ORDER BY started_at DESC,game_id DESC LIMIT ?""",
            args,
        )
    )


def rows(db, subject, limit, after):
    result = _side(db.connection, subject, "white", limit, after)
    result += _side(db.connection, subject, "black", limit, after)
    result.sort(key=lambda row: (row["started_at"], row["game_id"]), reverse=True)
    return result
