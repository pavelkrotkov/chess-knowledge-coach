"""Build bounded transfer selections with source- and corpus-bound scope."""

from .fact_fingerprint import canonical, digest
from .related_capture_candidates import candidates
from .related_capture_familiar import familiarity
from .related_capture_rank import rank
from .related_capture_source import baseline


def select(
    db,
    subject,
    source,
    corpus_version,
    version,
    *,
    theme="hangingPiece",
    all_lines=False,
    **matching,
):
    rating = baseline(db, source)
    familiar, games, is_familiar = familiarity(db, subject)
    pool, corpus = candidates(db, corpus_version, rating, games, theme=theme, all_lines=all_lines)
    if corpus is None:
        return None
    diagnostics = {}
    ordered = rank(source, pool, familiar, rating, diagnostics, is_familiar, **matching)
    scope = digest(
        canonical(
            [
                version,
                subject,
                source,
                corpus_version,
                corpus,
                rating,
                sorted(familiar),
                sorted(games),
                pool,
            ]
        )
    )
    return source, rating, corpus, ordered, scope, diagnostics
