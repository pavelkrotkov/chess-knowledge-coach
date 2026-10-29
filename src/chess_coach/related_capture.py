"""Preview and safely select bounded capture-transfer practice."""

from .fact_fingerprint import canonical, digest
from .related_capture_candidates import candidates
from .related_capture_cursor import _cursor, _offset
from .related_capture_familiar import familiarity
from .related_capture_features import capture_features
from .related_capture_rank import rank
from .related_capture_source import baseline, source_for_position

VERSION = "capture-transfer-v1"
PAGE = 4


def _selection(db, subject, position, corpus_version):
    source = source_for_position(db, subject, position)
    if capture_features(source["prompt_fen"], source["lines"][0].split()) is None:
        raise ValueError("unsupported capture source")
    rating = baseline(db, source)
    familiar, games, is_familiar = familiarity(db, subject)
    pool, corpus = candidates(db, corpus_version, rating, games)
    if corpus is None:
        return None
    diagnostics = {}
    ordered = rank(source, pool, familiar, rating, diagnostics, is_familiar)
    scope = digest(
        canonical(
            [
                VERSION,
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


def preview(db, subject, position, corpus_version, cursor=None):
    selection = _selection(db, subject, position, corpus_version)
    if selection is None:
        return {"status": "corpus unavailable", "items": [], "next_cursor": None}
    source, rating, corpus, ordered, scope, diagnostics = selection
    offset = _offset(cursor, scope)
    selected = ordered[offset : offset + PAGE]
    items = [_present(item, scope) for item in selected]
    return {
        "status": "available"
        if ordered
        else "insufficient compatible unfamiliar examples in the bounded scan",
        "items": items,
        "next_cursor": _cursor(offset + PAGE, scope) if offset + PAGE < len(ordered) else None,
        "review_status": source["provenance"]["review_status"],
        "baseline": rating,
        "bounds": [corpus["lower"], corpus["upper"]],
        "scanned": corpus["scanned"],
        "public_scanned": corpus["public"]["scanned"],
        "excluded": diagnostics,
        "selection": corpus["selection"],
        "scope": scope,
    }


def _present(item, scope):
    result = {
        key: value
        for key, value in item.items()
        if key not in {"order", "prompt_key", "key", "game", "diversity", "round"}
    }
    result["reference"] = digest(canonical([scope, item["type"], item["version"], item["key"]]))
    return result
