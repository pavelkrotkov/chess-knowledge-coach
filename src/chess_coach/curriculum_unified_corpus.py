"""Recheck a scheduled corpus mate reference."""

from .curriculum_candidates import verified_candidate
from .unified_corpus_mate import GOAL, apply
from .unified_source_current import snapshot_hash
from .unified_sources import resolve_source


def candidate(db, ref):
    record = db.connection.execute(
        """SELECT p.*,c.version,c.checksum FROM puzzles p
        JOIN puzzle_corpora c ON c.id=p.corpus_id
        WHERE c.version=? AND c.state='ready' AND p.puzzle_id=?""",
        ref[:2],
    ).fetchone()
    try:
        if record is None:
            return True, None
        source = resolve_source(db, "corpus", ref[0], ref[1])
        apply(db, source, "corpus", ref[0], ref[1], GOAL)
        if snapshot_hash(source) != ref[2]:
            return True, None
        result = verified_candidate(record)
        return True, ({**result, "unified_training": True} if result else None)
    except (TypeError, ValueError, KeyError, IndexError):
        return True, None
