"""Revalidate unified mate evidence against its current immutable lineage."""

import chess

from .mastery_position import position_key
from .mastery_unified_validation import check_evidence, check_time
from .unified_corpus_mate import is_source
from .unified_session_state import session_row
from .unified_source_current import require_current
from .unified_training_complete import _enrollment
from .unified_training_terminal import terminal


def _lineage(db, evidence, completion):
    row = session_row(db, completion["attempt_id"], completion["session_subject"])
    from .unified_training_canonical_promotion import is_forced_source
    from .unified_training_canonical_promotion import is_source as canonical_source

    if is_forced_source(row):
        from . import unified_canonical_forced_learning
        from .mastery_unified_capture import lineage

        return lineage(db, evidence, completion, row, policy=unified_canonical_forced_learning)

    if canonical_source(row):
        from . import unified_canonical_promotion_learning
        from .mastery_unified_capture import lineage

        return lineage(db, evidence, completion, row, policy=unified_canonical_promotion_learning)
    from .unified_training_public_mate import is_source as public_source

    if public_source(row):
        from . import unified_public_mate_learning
        from .mastery_unified_capture import lineage

        return lineage(db, evidence, completion, row, policy=unified_public_mate_learning)
    from .unified_training_owned_capture import is_source as capture_source

    if capture_source(row):
        from .mastery_unified_capture import lineage

        return lineage(db, evidence, completion, row)
    from .unified_training_owned_fork import is_source as fork_source

    if fork_source(row):
        from .mastery_unified_fork import lineage

        return lineage(db, evidence, completion, row)
    if not is_source(row):
        raise ValueError("source is not qualified")
    require_current(db, row)
    item = _enrollment(db, row)
    event, fact, assisted = terminal(db, row, completion["event_id"])
    check_evidence(evidence, completion, row, item, event, fact, assisted)
    check_time(evidence, completion, row)
    return {
        "kind": "training",
        "attempt_id": row["attempt_id"],
        "prompt_fen": position_key(chess.Board(row["prompt_fen"])),
    }


def training_context(db, evidence):
    if db.compat32:
        return None, "invalid_training_lineage"
    completion = db.connection.execute(
        """SELECT c.*,e.subject,s.subject AS session_subject,t.item_id,t.rating,t.reviewed_at,
        m.context_json AS evidence_context
        FROM unified_training_completions c
        JOIN unified_training_enrollments e ON e.attempt_id=c.attempt_id
        JOIN unified_sessions s ON s.attempt_id=c.attempt_id
        JOIN evidence_mappings m ON m.id=c.evidence_id
        JOIN training_attempts t ON t.id=c.training_attempt_id WHERE c.evidence_id=?""",
        (evidence["id"],),
    ).fetchone()
    if completion is None:
        return None, "invalid_training_lineage"
    try:
        return _lineage(db, evidence, completion), None
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        return None, "invalid_training_lineage"
