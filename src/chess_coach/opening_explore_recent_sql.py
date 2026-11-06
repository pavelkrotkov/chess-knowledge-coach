"""SQL-project bounded text before loading any game into Python."""

from .objective_source_budget import MAX_GAME_BYTES
from .style_time_projection import VERSION

NAME_CHARS = 256


def load(connection, game_id):
    return connection.execute(
        """SELECT g.id,
        CASE WHEN length(substr(CAST(g.white AS BLOB),1,?))<=? THEN g.white END AS white,
        CASE WHEN length(substr(CAST(g.black AS BLOB),1,?))<=? THEN g.black END AS black,
        CASE WHEN length(substr(CAST(g.pgn AS BLOB),1,?))<=? THEN g.pgn END AS pgn,
        t.started_at AS projected_start,
        CASE WHEN length(substr(CAST(t.white_identity AS BLOB),1,?))<=? THEN t.white_identity END AS projected_white,
        CASE WHEN length(substr(CAST(t.black_identity AS BLOB),1,?))<=? THEN t.black_identity END AS projected_black
        FROM games g JOIN style_game_times t ON t.game_id=g.id
        WHERE g.id=? AND t.status='current' AND t.version=?""",
        (
            NAME_CHARS + 1,
            NAME_CHARS,
            NAME_CHARS + 1,
            NAME_CHARS,
            MAX_GAME_BYTES + 1,
            MAX_GAME_BYTES,
            NAME_CHARS + 1,
            NAME_CHARS,
            NAME_CHARS + 1,
            NAME_CHARS,
            game_id,
            VERSION,
        ),
    ).fetchone()
