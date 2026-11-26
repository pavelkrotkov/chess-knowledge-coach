"""Resume legacy root attribution without changing preserved outcomes."""

from .capture_game_root_budget import fit, fits, record
from .fact_fingerprint import canonical, digest
from .short_mate_game_source import prepare, recheck
from .short_mate_trend_cohort import fingerprint
from .short_mate_trend_turns import inspect as inspect_turns

VERSION = "capture-root-refresh-v1"


def _marker(item, index):
    return {
        "version": VERSION,
        "identity": item["identity"],
        "signature": item["signature"],
        "next": index,
        "prefix": digest(canonical(item["results"][:index])),
    }


def _cursor(item):
    saved = item.get("root_refresh")
    if not isinstance(saved, dict):
        return 0
    index = saved.get("next")
    if type(index) is not int or not 0 <= index <= len(item["results"]):
        return 0
    return index if saved == _marker(item, index) else 0


def remember(state, item, first):
    cursor = _cursor(item)
    if cursor == first and (first == 0 or "root_refresh" in item):
        previous = item.get("root_refresh")
        item["root_refresh"] = _marker(item, len(item["results"]))
        fit(state)
        if not fits(state):
            if previous is None:
                item.pop("root_refresh", None)
            else:
                item["root_refresh"] = previous


def _admit(state, item, cursor):
    old = item.get("root_refresh")
    # Reserve the largest index before proving, while retaining the real cursor.
    item["root_refresh"] = _marker(item, len(item["results"]))
    fit(state)
    if not fits(state):
        if old is None:
            item.pop("root_refresh", None)
        else:
            item["root_refresh"] = old
        return False
    item["root_refresh"] = _marker(item, cursor)
    return True


def _source_current(db, learner, item):
    try:
        source = prepare(db, learner, item["id"])
        if (source["identity"], fingerprint(source["signature"])) != (
            item["identity"],
            item["signature"],
        ):
            return False
        recheck(db, learner, source)
        return True
    except (ValueError, TypeError, IndexError):
        return False


def _attach(state, item, rows, details, original):
    existing = {turn["position_id"] for turn in (item.get("root_details") or {}).get("turns", ())}
    for row, detail, expected in zip(rows, details, original, strict=False):
        if row == expected and detail and row[0] not in existing:
            record(state, item, row, detail)


def inspect(db, learner, item, deadline, quota, *, state, classifier, seconds):
    cursor = _cursor(item)
    if cursor == len(item["results"]) or not _source_current(db, learner, item):
        return 0
    if not _admit(state, item, cursor):
        return 0
    original = item["results"]
    shadow = {**item, "results": original[:cursor]}
    details = []

    def classify(board, played, until, clock):
        value = {}
        result = classifier(board, played, until, clock, details=value)
        details.append(value)
        return result

    try:
        inspect_turns(db, learner, shadow, deadline, quota, classifier=classify, seconds=seconds)
    except (ValueError, TypeError, IndexError):
        item["root_refresh"] = _marker(item, cursor)
        return len(details)
    _attach(state, item, shadow["results"][cursor:], details, original[cursor:])
    # The source was rechecked by inspect_turns; even an expired attempt was charged.
    item["root_refresh"] = _marker(item, cursor + len(details))
    return len(details)
