"""Find a cheap stored named-opening boundary for nominations only."""

from . import opening_decision_budget as pinned


def boundary(db, game_id):
    opening = db.connection.execute(
        """SELECT CASE WHEN length(substr(CAST(d.version AS BLOB),1,201))<=200 THEN d.version END AS version,
        CASE WHEN length(substr(CAST(d.source_url AS BLOB),1,201))<=200 THEN d.source_url END AS source_url, d.content_revision,
        CASE WHEN length(substr(CAST(n.position_key AS BLOB),1,201))<=200 THEN n.position_key END AS position_key,
        CASE WHEN length(substr(CAST(r.classifier_version AS BLOB),1,201))<=200 THEN r.classifier_version END AS classifier_version
        FROM current_game_openings o JOIN opening_datasets d ON d.id=o.dataset_id
        JOIN opening_runs r ON r.id=o.run_id
        LEFT JOIN opening_nodes n ON n.id=o.opening_node_id WHERE o.game_id=?""",
        (game_id,),
    ).fetchone()
    if opening is None or not opening["position_key"] or len(opening["position_key"]) > 200:
        return 0
    identity = (
        opening["version"],
        opening["source_url"],
        opening["classifier_version"],
        opening["content_revision"],
    )
    if identity != (pinned.VERSION, pinned.SOURCE, pinned.CLASSIFIER_VERSION, 1):
        return 0
    row = db.connection.execute(
        """SELECT ply FROM positions WHERE game_id=? AND ply<=?
        AND length(substr(CAST(fen AS BLOB),1,201))<=200
        AND instr(substr(CAST(fen AS BLOB),1,201), CAST(? AS BLOB))=1
        ORDER BY ply DESC LIMIT 1""",
        (game_id, pinned.MAX_POSITIONS, opening["position_key"] + " "),
    ).fetchone()
    return row["ply"] if row else 0
