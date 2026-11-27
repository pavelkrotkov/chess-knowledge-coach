"""Replay both source-bound harder lineages under one caller deadline."""

from .capture_harder_lineage import verify as verify_capture
from .fork_harder_lineage import verify as verify_fork


def verify(db, subject, corpus, capture, fork, as_of, check):
    if fork["controls"]["admission"] == "harder":
        verify_capture(db, subject, corpus, capture["source"], check)
        verify_fork(db, subject, corpus, fork, as_of, check)
