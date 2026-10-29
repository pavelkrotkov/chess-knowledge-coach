"""Atomically record one completed attempt after rechecking its selection."""

from .analysis_comparison import save_comparison
from .analysis_engine import create_run
from .deep_execution_completeness import completeness
from .deep_execution_selection import current_selection
from .deep_execution_stability import stability
from .deep_execution_state import finish_state, mark_stale
from .fact_fingerprint import canonical
from .mapping_transaction import mapping_transaction


def finish_attempt(db, job, attempt_id, learner, binary, metadata, config, position, board, result):
    with mapping_transaction(db):
        try:
            selection = current_selection(db, job["selection_id"], learner)
        except ValueError:
            return mark_stale(db, job, attempt_id)
        detail = completeness(result, board, position["uci"], config["min_depth"])
        comparison, unstable = ("unknown", False)
        if detail is None:
            comparison, unstable = stability(db, selection, position, board, result, config)
        status = "insufficient" if detail else "unstable" if unstable else "complete"
        detail = detail or ("score_disagreement" if unstable else "search_complete")
        run_id = create_run(db.connection, selection["game_id"], binary, metadata, config)
        save_comparison(db.connection, run_id, result["best"])
        save_comparison(db.connection, run_id, result["played"])
        db.connection.executemany(
            "INSERT INTO deep_analysis_alternatives(attempt_id,rank,line_json) VALUES(?,?,?)",
            [
                (attempt_id, item["rank"], canonical(item["line"]))
                for item in result["alternatives"]
            ],
        )
        finish_state(db, job["id"], attempt_id, status, detail, comparison, run_id, result)
        return {
            "job_id": job["id"],
            "position_id": job["position_id"],
            "status": status,
            "comparison": comparison,
            "detail": detail,
        }


def finish_error(db, job, attempt_id, learner, detail):
    with mapping_transaction(db):
        try:
            current_selection(db, job["selection_id"], learner)
        except ValueError:
            return mark_stale(db, job, attempt_id)
        finish_state(db, job["id"], attempt_id, "insufficient", detail, "unknown", None, None)
        return {
            "job_id": job["id"],
            "position_id": job["position_id"],
            "status": "insufficient",
            "comparison": "unknown",
            "detail": detail,
        }
