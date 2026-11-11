"""Select a bounded, source-checked capture example from recorded failures."""

from collections import Counter, defaultdict
from datetime import UTC, datetime

from .learner_identity import normalize_identity
from .material_policy import MAPPER
from .recurrence_cursor import MAX_ID
from .recurrence_selection import consider
from .recurrence_sources import evidence
from .related_capture_source import source_for_position
from .unified_own_game import VERSION
from .unified_own_game_snapshot import key_for

SCAN = 20
SOURCE_CHECKS = 3


def _groups(db, learner, *, check=lambda: None, operation="execute"):
    rows, limited = evidence(
        db, learner, "hanging_piece", operation, MAX_ID, failure_only=True, limit=SCAN
    )
    cache, parts, excluded, seen = {}, {}, Counter(), set()
    groups = defaultdict(list)
    # Recheck only the bounded recent record page, not the full corpus.
    for row in rows:
        check()
        item = consider(
            db,
            learner,
            row,
            {},
            cache,
            parts,
            excluded,
            datetime(2, 1, 1, tzinfo=UTC),
            datetime.now(UTC),
            datetime(1, 1, 1, tzinfo=UTC),
        )
        check()
        if item is None or item["family"] != MAPPER:
            continue
        # Reimports of the same game and decision are one observation.
        identity = (item["game_key"], item["ply"], item["family"], item["version"])
        if identity in seen:
            continue
        seen.add(identity)
        groups[(item["family"], item["version"])].append(item)
    return groups, limited, len(rows)


def _finished(checked, stop):
    return checked >= SOURCE_CHECKS or stop()


def _source(db, learner, position, check):
    if check is None:
        return source_for_position(db, learner, position)
    return source_for_position(db, learner, position, check=check)


def witnesses(db, learner, groups, *, stop=lambda: False, check=None):
    ranked = sorted(
        groups.values(), key=lambda items: (-len({x["game_key"] for x in items}), -items[0]["id"])
    )
    # Resolve a small number of source witnesses after grouping the markers.
    checked = 0
    for items in ranked:
        for item in items:
            if _finished(checked, stop):
                return
            checked += 1
            try:
                source = _source(db, learner, item["position_id"], check)
                if source["provenance"]["evidence_id"] != item["id"]:
                    continue
                yield {
                    "position_id": item["position_id"],
                    "evidence_id": item["id"],
                    "games": len({x["game_key"] for x in items}),
                    "observations": len(items),
                    "reviewed": source["provenance"]["review_status"] == "accepted",
                    "version": VERSION,
                    "key": key_for(
                        {
                            "position_id": item["position_id"],
                            "objective": {"kind": source["objective"]},
                        },
                        item["id"],
                    ),
                }
            except (ValueError, TypeError, KeyError, IndexError):
                continue


def _chosen(db, learner, groups, *, check=None):
    return next(witnesses(db, learner, groups, check=check), None)


def choose(db, subject, *, check=None):
    learner = normalize_identity(subject)
    if not learner:
        raise ValueError("learner unavailable")
    options = {"check": check} if check is not None else {}
    groups, limited, scanned = _groups(db, learner, **options)
    return {
        "source": _chosen(db, learner, groups, check=check),
        "limited": limited,
        "scanned": scanned,
    }
