"""Attach bounded ready corpus practice choices to the private library."""

from .puzzle_query import _result
from .unified_corpus_mate_proof import eligible


def corpus_choices(db, corpora):
    for corpus in corpora:
        rows = db.connection.execute(
            """SELECT p.* FROM puzzles p JOIN puzzle_corpora c ON c.id=p.corpus_id
            WHERE c.version=? AND c.state IN ('ready','legacy_ready')
            ORDER BY p.rating,p.puzzle_id LIMIT 10""",
            (corpus["version"],),
        ).fetchall()
        corpus["practice_tasks"] = [
            {**_result(row), "mate_in_one": corpus["state"] == "ready" and eligible(row)}
            for row in rows
        ]
    return corpora
