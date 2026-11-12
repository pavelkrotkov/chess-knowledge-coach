"""Recheck source and prior exposures for one frozen recognition attempt."""

import json

from .recognition_proof import VERSION
from .recognition_verify import proof as verify_proof
from .related_capture_assessment import setup
from .related_capture_candidates import _game_id


def source(db, row):
    board, _, fingerprint = setup(db, row["source_version"], row["source_key"])
    proof = json.loads(row["proof_json"])
    if not isinstance(proof, dict):
        raise ValueError("recognition proof unavailable")
    if (fingerprint, board.fen(), proof.get("version"), proof.get("source_fingerprint")) != (
        row["source_fingerprint"],
        row["prompt_fen"],
        VERSION,
        fingerprint,
    ):
        raise ValueError("recognition source changed")
    data = db.connection.execute(
        """SELECT p.rating,p.rating_deviation,p.opening,p.source FROM puzzles p JOIN puzzle_corpora c
        ON c.id=p.corpus_id WHERE c.version=? AND p.puzzle_id=? AND c.state='ready'""",
        (row["source_version"], row["source_key"]),
    ).fetchone()
    if data is None or (data["rating"], data["rating_deviation"]) != (
        row["content_rating"],
        row["content_deviation"],
    ):
        raise ValueError("recognition source context changed")
    if data["opening"] != row["content_opening"]:
        raise ValueError("recognition source context changed")
    if data["source"] != row["source_url"] or _game_id(data["source"]) != row["source_game"]:
        raise ValueError("recognition source changed")
    verify_proof(proof)
    return board, proof
