"""Certify and recheck an explicit immediate-mate corpus objective."""

import json

from .fact_fingerprint import canonical, digest
from .unified_corpus_mate_proof import certify

GOAL = "mate_in_one"
OBJECTIVE = "corpus_mate_in_one"
KEY = "corpus_mate"
VERSION = "corpus-mate-in-one-v1"


def validate_goal(source_type, goal):
    if goal not in (None, GOAL) or (goal == GOAL and source_type != "corpus"):
        raise ValueError("unsupported practice goal")


def check_existing(row, goal):
    if (row["source_type"] == "corpus" and row["objective"] == OBJECTIVE) != (goal == GOAL):
        raise ValueError("attempt ID belongs to another goal")


def apply(db, snapshot, source_type, version, key, goal):
    if goal is None:
        return
    validate_goal(source_type, goal)
    # Only the exact ready row, including its original setup, may be bound.
    row = db.connection.execute(
        """SELECT p.fen,p.solution,c.checksum FROM puzzles p JOIN puzzle_corpora c
        ON c.id=p.corpus_id WHERE c.version=? AND p.puzzle_id=? AND c.state='ready'""",
        (version, key),
    ).fetchone()
    if row is None or certify(row) != snapshot["prompt_fen"]:
        raise ValueError("immediate mate source unavailable")
    source = [version, key, row["fen"], row["solution"], row["checksum"]]
    snapshot["objective"] = OBJECTIVE
    snapshot["provenance"][KEY] = {"version": VERSION, "source_sha256": digest(canonical(source))}


def is_source(row):
    if row["source_type"] != "corpus" or row["objective"] != OBJECTIVE:
        return False
    binding = json.loads(row["provenance_json"]).get(KEY)
    return isinstance(binding, dict) and binding.get("version") == VERSION
