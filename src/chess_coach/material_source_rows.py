"""Read exactly the active analysis rows used by material verification."""

from .deep_selection_source import learner_key


def deep_row(connection, position_id, game_id, learner):
    return connection.execute(
        """SELECT s.id AS selection_id,s.cheap_run_id,s.input_fingerprint,s.selector_version,
        j.id AS job_id,j.status AS job_status,j.config_fingerprint,j.config_json AS job_config,
        a.id AS attempt_id,a.status AS attempt_status,a.analysis_run_id,a.comparison,
        a.best_work_json,a.played_work_json
        FROM deep_selection_current c JOIN deep_selection_runs s ON s.id=c.selection_id
        LEFT JOIN deep_analysis_current dc ON dc.selection_id=s.id AND dc.position_id=?
        LEFT JOIN deep_analysis_jobs j ON j.id=dc.job_id
        LEFT JOIN deep_analysis_attempts a ON a.id=(SELECT id FROM deep_analysis_attempts
            WHERE job_id=j.id ORDER BY attempt_number DESC LIMIT 1)
        WHERE c.game_id=? AND c.learner_key=?""",
        (position_id, game_id, learner_key(learner)),
    ).fetchone()


def lines(connection, run_id):
    rows = connection.execute(
        "SELECT * FROM decision_analysis_lines WHERE run_id=? ORDER BY position_id,role", (run_id,)
    ).fetchall()
    return [dict(row) for row in rows]


def runs(connection, ids):
    return [
        dict(
            connection.execute(
                "SELECT id,game_id,config_json FROM analysis_runs WHERE id=?", (i,)
            ).fetchone()
        )
        for i in ids
    ]


def alternatives(connection, attempt_id):
    rows = connection.execute(
        "SELECT rank,line_json FROM deep_analysis_alternatives WHERE attempt_id=? ORDER BY rank",
        (attempt_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def completed(row):
    if (
        row
        and row["job_status"] == "complete"
        and row["attempt_status"] == "complete"
        and row["analysis_run_id"] is not None
    ):
        return row
    return None


def consumed_rows(connection, cheap_id, position_id, game_id, learner):
    deep = completed(deep_row(connection, position_id, game_id, learner))
    run_ids = [cheap_id, deep["analysis_run_id"]] if deep else [cheap_id]
    return {
        "cheap_lines": lines(connection, cheap_id),
        "deep": dict(deep) if deep else None,
        "runs": runs(connection, run_ids),
        "deep_lines": lines(connection, run_ids[-1]) if deep else [],
        "deep_alternatives": alternatives(connection, deep["attempt_id"]) if deep else [],
    }
