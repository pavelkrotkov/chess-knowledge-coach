"""Present related examples and bind their signed references."""

from .fact_fingerprint import canonical, digest
from .related_capture_cursor import PAGE, _cursor, _offset
from .related_capture_ready import entries as prepared_entries
from .related_mate_search_token import fingerprint


def unavailable(window):
    entries = (*window["entries"].values(), *window["public"]["entries"].values())
    return sum(entry.get("reason") == "exchange_unresolved" for entry in entries)


def _assessment_options(db, visible, ordered, cursor, scope, subject, *, window=None):
    from .related_capture_assessment import setup
    from .tactical_exposure_admission import eligible

    offset = _offset(cursor, scope)
    prepared = prepared_entries(window) if window is not None else None
    for item, source in zip(visible, ordered[offset : offset + PAGE], strict=True):
        if source["type"] != "corpus":
            continue
        if prepared is not None and prepared.get(source["key"], {}).get("assessment") is None:
            continue
        # Eligibility is cheap; admission uses the prepared capture proof.
        try:
            setup(db, source["version"], source["key"])
            if eligible(db, subject, source):
                item["assessment_available"] = True
            else:
                item["assessment_reason"] = "provided or exposure coverage unavailable"
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
        result["reference"] = fingerprint(secret, "capture-reference", identity)
    return result


def _reference(selected, reference, secret, *, finder=False):
    if secret is None:
        if finder:
            raise ValueError("capture finder unavailable")
        return reference
    scope = selected[4]
    for item in selected[3]:
        identity = [scope, item["type"], item["version"], item["key"]]
        if fingerprint(secret, "capture-reference", identity) == reference:
            return digest(canonical(identity))
    raise ValueError("capture selection changed")
