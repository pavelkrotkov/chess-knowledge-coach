"""Attach bounded ready corpus practice choices to the private library."""

from .puzzle_query import query_puzzles


def corpus_choices(db, corpora):
    for corpus in corpora:
        corpus["practice_tasks"] = query_puzzles(db, version=corpus["version"], limit=10)
    return corpora
