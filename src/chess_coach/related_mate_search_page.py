"""Present one bounded continuation batch and its next step."""

from .related_capture import present
from .related_capture_cursor import _cursor
from .related_mate import _assessment_options
from .related_mate_search_corpus import seed
from .related_mate_search_next import advance
from .related_mate_search_select import select
from .related_mate_search_token import decode, encode, fingerprint


def preview(db, subject, evidence, version, token, secret):
    state = (
        seed(db, subject, evidence, version, secret) if token == "begin" else decode(secret, token)
    )
    if state is None:
        return {
            "status": "Search stopped at the continuation limit.",
            "items": [],
            "search_mode": True,
            "search_limited": True,
        }
    chosen, next_keys = select(db, subject, evidence, version, secret, state)
    source, _, _, ordered, scope, _ = chosen
    offset = state["offset"]
    cursor = _cursor(offset, scope) if offset else None
    result = present(chosen, cursor)
    if not result["items"]:
        result["status"] = "No matching examples in this batch"
    _assessment_options(db, result["items"], ordered, scope)
    next_state, limited = advance(secret, state, chosen, next_keys)
    result.update(
        search_mode=True,
        form_search=encode(secret, {**state, "scope": fingerprint(secret, "scope", scope)}),
        next_search=encode(secret, next_state) if next_state else None,
        search_limited=limited,
        search_more_matches=bool(next_state and next_state["scope"]),
        next_cursor=None,
        source_outcome=source["outcome"],
        mate_timing=source["objective"],
    )
    return result
