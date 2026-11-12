"""Check selected patterns against their recorded coverage and omissions."""

from .tactical_course_related import FORK_CORPUS, FORK_EMPTY, GENERAL_EMPTY, HISTORY_LIMIT
from .tactical_course_selection import CURRENT_PAIRS, PAIRS

OWN = "owned source unavailable"
UNSUPPORTED = "related matching unsupported"
RELATED = {
    UNSUPPORTED,
    "related matching deferred: time budget",
    GENERAL_EMPTY,
    FORK_CORPUS,
    FORK_EMPTY,
    HISTORY_LIMIT,
}


def _valid_reason(pair, reason, pairs):
    # Only v2 non-protection matchers can omit work for the shared history cap.
    if reason == HISTORY_LIMIT:
        return pairs == CURRENT_PAIRS and pair != ("hanging_piece", "prevent")
    if reason in {FORK_CORPUS, FORK_EMPTY}:
        return pair == ("fork", "execute")
    return pair != ("fork", "execute") or reason != GENERAL_EMPTY


def omissions(selection, *, pairs=PAIRS):
    result = {}
    coverage = {(row["skill"], row["operation"]): row for row in selection["coverage"]}
    for item in selection["unavailable"]:
        pair = (item["skill"], item["operation"])
        reason = item["reason"]
        if pair not in pairs or pair in result or reason not in RELATED | {OWN}:
            raise ValueError("invalid preview omission")
        if not _valid_reason(pair, reason, pairs):
            raise ValueError("fork omission differs")
        if coverage[pair]["status"] != "complete":
            raise ValueError("omission has incomplete coverage")
        result[pair] = reason
    return result


def selected(pattern, chapters, gaps):
    pair = (pattern["skill"], pattern["operation"])
    reason = gaps.get(pair)
    if reason == OWN or (reason is None) != (len(chapters) == 2):
        raise ValueError("related chapter and omission differ")
    if (reason == UNSUPPORTED) != (pattern["kind"] == "protection"):
        raise ValueError("unsupported related pattern differs")
