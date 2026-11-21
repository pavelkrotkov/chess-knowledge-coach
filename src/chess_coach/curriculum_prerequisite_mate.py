"""Check one ready corpus mate and its known coach exposure."""

from .tactical_exposure_check import check as exposure
from .unified_corpus_mate_proof import certify


def _row(db, version, key):
    return db.connection.execute(
        """SELECT p.fen,p.solution,c.checksum FROM puzzles p JOIN puzzle_corpora c
        ON c.id=p.corpus_id WHERE c.version=? AND p.puzzle_id=? AND c.state='ready'""",
        (version, key),
    ).fetchone()


def prompt(db, subject, version, key):
    row = _row(db, version, key)
    if row is None:
        raise ValueError("diagnostic source unavailable")
    fen = certify(row)
    key_fen = " ".join(fen.split()[:4])
    if exposure(db, subject, key_fen) != "not_recorded":
        raise ValueError("diagnostic exposure unavailable")
    return key_fen
