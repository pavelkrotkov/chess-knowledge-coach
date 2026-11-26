"""Resume legacy root attribution without changing preserved outcomes."""

from .capture_game_root_budget import PROOF_VERSION, VERSION, record
from .capture_game_root_checkpoint import VERSION as REFRESH_VERSION
from .capture_game_root_checkpoint import admit, cursor, marker
from .short_mate_game_source import prepare, recheck
from .short_mate_trend_cohort import fingerprint
from .short_mate_trend_turns import inspect as inspect_turns


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


def _attach(state, item, rows, details, original, version, proof):
    existing = {turn["position_id"] for turn in (item.get("root_details") or {}).get("turns", ())}
    for row, detail, expected in zip(rows, details, original, strict=False):
        if row == expected and detail and row[0] not in existing:
            record(state, item, row, detail, version=version, proof=proof)


def inspect(
    db,
    learner,
    item,
    deadline,
    quota,
    *,
    state,
    classifier,
    seconds,
    version=VERSION,
    proof=PROOF_VERSION,
    refresh_version=REFRESH_VERSION,
):
    offset = cursor(item, version=refresh_version)
    if offset == len(item["results"]) or not _source_current(db, learner, item):
        return 0
    if not admit(state, item, offset, version=refresh_version):
        return 0
    original = item["results"]
    shadow = {**item, "results": original[:offset]}
    details = []

    def classify(board, played, until, clock):
        value = {}
        result = classifier(board, played, until, clock, details=value)
        details.append(value)
        return result

    try:
        inspect_turns(db, learner, shadow, deadline, quota, classifier=classify, seconds=seconds)
    except (ValueError, TypeError, IndexError):
        item["root_refresh"] = marker(item, offset, version=refresh_version)
        return len(details)
    _attach(state, item, shadow["results"][offset:], details, original[offset:], version, proof)
    # The source was rechecked by inspect_turns; even an expired attempt was charged.
    item["root_refresh"] = marker(item, len(shadow["results"]), version=refresh_version)
    return len(details)
