"""Search bounded, unpredictable corpus families for a supported prompt."""

import secrets

from .recognition_candidate import candidate as candidate_for
from .related_corpus_window import corpus_rows

PER_BAND = 100
THEMES = (("capture", "hangingPiece"), ("mate", "mateIn1"))


def scan(db, subject, version, corpus, familiar, games, seen, check):
    ordered = THEMES if secrets.randbelow(2) == 0 else THEMES[::-1]
    for kind, theme in ordered:
        rows, _ = corpus_rows(db, corpus, 600, 2200, theme, PER_BAND)
        for row in rows:
            check()
            result = candidate_for(db, subject, version, row, kind, familiar, games, seen, check)
            if result:
                return result
    return None
