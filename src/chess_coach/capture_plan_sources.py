"""Select a bounded, source-checked capture example from recorded failures."""

from collections import Counter, defaultdict
from datetime import UTC, datetime

from .learner_identity import normalize_identity
from .material_policy import MAPPER
from .recurrence_cursor import MAX_ID
from .recurrence_selection import consider
from .recurrence_sources import evidence
from .related_capture_source import source_for_position

SCAN = 20
SOURCE_CHECKS = 3


def _groups(db, learner):
    rows, limited = evidence(
        db, learner, "hanging_piece", "execute", MAX_ID, failure_only=True, limit=SCAN
    )
    cache, parts, excluded, seen = {}, {}, Counter(), set()
    groups = defaultdict(list)
    # Recheck only the bounded recent record page, not the full corpus.
    for row in rows:
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
        if item is None or item["family"] != MAPPER:
            continue
        # Reimports of the same game and decision are one observation.
        identity = (item["game_key"], item["ply"], item["family"], item["version"])
        if identity in seen:
            continue
        seen.add(identity)
        groups[(item["family"], item["version"])].append(item)
    return groups, limited, len(rows)


def _chosen(db, learner, groups):
    ranked = sorted(
        groups.values(), key=lambda items: (-len({x["game_key"] for x in items}), -items[0]["id"])
    )
    # Resolve a small number of source witnesses after grouping the markers.
    checked = 0
    for items in ranked:
        for item in items:
            if checked >= SOURCE_CHECKS:
                return None
            checked += 1
            try:
                source = source_for_position(db, learner, item["position_id"])
                if source["provenance"]["evidence_id"] != item["id"]:
                    continue
                return {
                    "position_id": item["position_id"],
                    "games": len({x["game_key"] for x in items}),
                    "observations": len(items),
                    "reviewed": source["provenance"]["review_status"] == "accepted",
                }
            except (ValueError, TypeError, KeyError, IndexError):
                continue
    return None


def choose(db, subject):
    learner = normalize_identity(subject)
    if not learner:
        raise ValueError("learner unavailable")
    groups, limited, scanned = _groups(db, learner)
    return {"source": _chosen(db, learner, groups), "limited": limited, "scanned": scanned}
