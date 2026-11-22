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


def retry_unavailable(state, found, info):
    if state["v"] not in {5, 6} or not found or not info:
        return False
    if info.get("diagnostic") != "unavailable" or state["prerequisite_offered"]:
        return False
    # This candidate was not offered; retain its scanned coordinate, not its selection.
    prompt_key = found[0]["prompt_key"]
    state["seen"] = [key for key in state["seen"] if key != prompt_key]
    return True
