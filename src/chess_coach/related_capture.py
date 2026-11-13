"""Preview and safely select bounded capture-transfer practice."""

from .fact_fingerprint import canonical, digest
from .related_capture_cursor import _cursor, _offset
from .related_capture_features import capture_features
from .related_capture_source import source_for_position
from .related_transfer_select import select

VERSION = "capture-transfer-v1"
PAGE = 4


def _selection(
    db, subject, position, corpus_version, *, familiar_data=None, rating_bounds=None, score=None
):
    source = source_for_position(db, subject, position)
    if capture_features(source["prompt_fen"], source["lines"][0].split()) is None:
        raise ValueError("unsupported capture source")
    options = {"rating_bounds": rating_bounds} if rating_bounds is not None else {}
    if score is not None:
        options["score"] = score
    return select(
        db, subject, source, corpus_version, VERSION, familiar_data=familiar_data, **options
    )


def preview(db, subject, position, corpus_version, cursor=None, *, secret=None):
    selection = _selection(db, subject, position, corpus_version)
    result = present(selection, cursor, secret=secret)
    # Only the browser receives opaque references and assessment controls.
    if selection is not None and secret is not None:
        _assessment_options(db, result["items"], selection[3], cursor, result["scope"])
    return result


def _assessment_options(db, visible, ordered, cursor, scope):
    from .related_capture_assessment import setup

    offset = _offset(cursor, scope)
    for item, source in zip(visible, ordered[offset : offset + PAGE], strict=True):
        if source["type"] != "corpus":
            continue
        # Eligibility is cheap; admission separately runs the capture proof.
        try:
            setup(db, source["version"], source["key"])
            item["assessment_available"] = True
        except (ValueError, TypeError, KeyError, IndexError):
            continue


def present(selection, cursor, *, secret=None):
    if selection is None:
        return {"status": "corpus unavailable", "items": [], "next_cursor": None}
    source, rating, corpus, ordered, scope, diagnostics = selection
    # A cursor may expose its tag, so reference MACs use the hidden scope itself.
    if secret is not None:
        from .related_mate_search_token import fingerprint

        cursor_scope = fingerprint(secret, "capture-scope", scope)
    else:
        cursor_scope = scope
    offset = _offset(cursor, cursor_scope)
    selected = ordered[offset : offset + PAGE]
    items = [_present(item, scope, secret) for item in selected]
    return {
        "status": "available"
        if ordered
        else "insufficient compatible unfamiliar examples in the bounded scan",
        "items": items,
        "next_cursor": _cursor(offset + PAGE, cursor_scope)
        if offset + PAGE < len(ordered)
        else None,
        "review_status": source["provenance"]["review_status"],
        "baseline": rating,
        "bounds": [corpus["lower"], corpus["upper"]],
        "scanned": corpus["scanned"],
        "public_scanned": corpus["public"]["scanned"],
        "excluded": diagnostics,
        "selection": corpus["selection"],
        "scope": cursor_scope,
    }


def _present(item, scope, secret=None):
    result = {
        key: value
        for key, value in item.items()
        if key
        not in {
            "order",
            "prompt_key",
            "key",
            "game",
            "diversity",
            "round",
            "matching_lines",
            "matching_line_indices",
            "source_lines_hash",
        }
    }
    identity = [scope, item["type"], item["version"], item["key"]]
    if secret is None:
        result["reference"] = digest(canonical(identity))
    else:
        from .related_mate_search_token import fingerprint

        result["reference"] = fingerprint(secret, "capture-reference", identity)
    return result
