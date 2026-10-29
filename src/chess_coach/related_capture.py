"""Preview and safely select bounded capture-transfer practice."""

from .fact_fingerprint import canonical, digest
from .related_capture_cursor import _cursor, _offset
from .related_capture_features import capture_features
from .related_capture_source import source_for_position
from .related_transfer_select import select

VERSION = "capture-transfer-v1"
PAGE = 4


def _selection(db, subject, position, corpus_version):
    source = source_for_position(db, subject, position)
    if capture_features(source["prompt_fen"], source["lines"][0].split()) is None:
        raise ValueError("unsupported capture source")
    return select(db, subject, source, corpus_version, VERSION)


def preview(db, subject, position, corpus_version, cursor=None):
    selection = _selection(db, subject, position, corpus_version)
    return present(selection, cursor)


def present(selection, cursor):
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
    result["reference"] = digest(canonical([scope, item["type"], item["version"], item["key"]]))
    return result
