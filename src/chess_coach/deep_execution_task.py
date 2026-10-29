"""Run one selected position with private spooling and atomic finalization."""

from tempfile import TemporaryFile

from .decision_history import decision_board
from .deep_execution_finish import finish_attempt, finish_error
from .deep_execution_search import search


def execute_job(db, job, attempt_id, learner, binary, engine, metadata, config):
    try:
        position = db.connection.execute(
            "SELECT * FROM positions WHERE id=?", (job["position_id"],)
        ).fetchone()
        if position is None:
            raise ValueError("decision is unavailable")
        board = decision_board(db, position)
        if db.connection.in_transaction:
            raise RuntimeError("engine work cannot run inside a transaction")
        with TemporaryFile(mode="w+t", encoding="utf-8", dir=db.path.parent) as spool:
            result = search(engine, board, position, config, spool)
        output = finish_attempt(
            db, job, attempt_id, learner, binary, metadata, config, position, board, result
        )
        return output, result["engine_broken"]
    except Exception:
        return finish_error(db, job, attempt_id, learner, "processing_failed"), True
