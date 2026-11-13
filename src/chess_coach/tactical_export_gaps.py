"""Check selected patterns against their recorded coverage and omissions."""

from .tactical_course_related import (
    FORK_CORPUS,
    FORK_EMPTY,
    GENERAL_EMPTY,
    HISTORY_LIMIT,
    PROTECTION_CORPUS,
    PROTECTION_EMPTY,
    PROTECTION_LIMIT,
    PROTECTION_SOURCE,
)
from .tactical_course_selection import CURRENT_PAIRS, PAIRS

OWN = "owned source unavailable"
OWN_DEFERRED = "owned source deferred: time budget"
OWN_REASONS = {OWN, OWN_DEFERRED}
UNSUPPORTED = "related matching unsupported"
RELATED = {
    UNSUPPORTED,
    "related matching deferred: time budget",
    GENERAL_EMPTY,
    FORK_CORPUS,
    FORK_EMPTY,
    HISTORY_LIMIT,
    PROTECTION_CORPUS,
    PROTECTION_EMPTY,
    PROTECTION_LIMIT,
    PROTECTION_SOURCE,
}


def _valid_reason(pair, reason, pairs, modern):
    # Only v2 non-protection matchers can omit work for the shared history cap.
    if reason == HISTORY_LIMIT:
        return pairs == CURRENT_PAIRS and (modern or pair != ("hanging_piece", "prevent"))
    if reason in {PROTECTION_CORPUS, PROTECTION_EMPTY, PROTECTION_LIMIT, PROTECTION_SOURCE}:
        return modern and pair == ("hanging_piece", "prevent")
    if reason in {FORK_CORPUS, FORK_EMPTY}:
        return pair == ("fork", "execute")
    return pair != ("fork", "execute") or reason != GENERAL_EMPTY


def _allowed(pair, reason, pairs, seen, owned_deadline):
    return (
        pair in pairs
        and pair not in seen
        and reason in RELATED | OWN_REASONS
        and (reason != OWN_DEFERRED or owned_deadline)
    )


def omissions(selection, *, pairs=PAIRS, modern=False, owned_deadline=False):
    result = {}
    coverage = {(row["skill"], row["operation"]): row for row in selection["coverage"]}
    for item in selection["unavailable"]:
        pair = (item["skill"], item["operation"])
        reason = item["reason"]
        if not _allowed(pair, reason, pairs, result, owned_deadline):
            raise ValueError("invalid preview omission")
        if not _valid_reason(pair, reason, pairs, modern):
            raise ValueError("fork omission differs")
        if coverage[pair]["status"] != "complete":
            raise ValueError("omission has incomplete coverage")
        result[pair] = reason
    return result


def selected(pattern, chapters, gaps, *, modern=False):
    pair = (pattern["skill"], pattern["operation"])
    reason = gaps.get(pair)
    if reason in OWN_REASONS or (reason is None) != (len(chapters) == 2):
        raise ValueError("related chapter and omission differ")
    if (reason == UNSUPPORTED) != (pattern["kind"] == "protection" and not modern):
        raise ValueError("unsupported related pattern differs")
