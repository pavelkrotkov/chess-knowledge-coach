"""Page through current private sources for one bounded protection transfer."""

import sqlite3
import time

from .learner_identity import normalize_identity
from .protection_finder_cursor import state_for
from .protection_finder_scan import Finder
from .protection_finder_work import SourceChecks

SECONDS = 40.0


def find(db, subject, corpus, secret, cursor=None):
    identity = normalize_identity(subject)
    if not identity or db.connection.in_transaction:
        raise ValueError("finder unavailable")
    signer, state = state_for(secret, subject, corpus, cursor)
    until = time.monotonic() + SECONDS
    search = Finder(db, identity, state, SourceChecks(db, subject, corpus, until))
    db.connection.set_progress_handler(lambda: int(time.monotonic() >= until), 1000)
    try:
        try:
            # Keep later imports outside both phases of this search.
            if not cursor:
                watermark = _watermark(db, identity)
                state[2:] = [watermark, watermark, watermark, 0]
            search.run()
        except TimeoutError:
            search.partial = True
        except sqlite3.OperationalError as error:
            if error.sqlite_errorcode != sqlite3.SQLITE_INTERRUPT:
                raise
            search.partial = True
    finally:
        db.connection.set_progress_handler(None, 0)

    return {
        "result": search.checks.result,
        "scanned": search.scanned,
        "checked": search.checks.checked,
        "partial": search.partial,
        "next_cursor": None if search.finished else signer.dumps(search.state),
    }


def _watermark(db, identity):
    row = db.connection.execute(
        """SELECT id FROM evidence_mappings INDEXED BY idx_curriculum_evidence
        WHERE subject=? AND skill='hanging_piece' AND operation='prevent'
        ORDER BY id DESC LIMIT 1""",
        (identity,),
    ).fetchone()
    return min(row["id"] + 1, 2**63 - 1) if row else 2**63 - 1
