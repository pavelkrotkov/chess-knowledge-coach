"""Recheck the failure sources in one bounded skill page."""

from datetime import UTC, datetime

from .lesson_mechanisms import describe
from .lesson_source import source
from .recurrence_selection import consider


def collect_page(db, learner, history, rows, groups, excluded, seen):
    cache, parts = {}, {}
    previous = datetime(1, 1, 1, tzinfo=UTC)
    begin = datetime(2, 1, 1, tzinfo=UTC)
    finish = datetime.now(UTC)
    for row in rows:
        item = consider(
            db, learner, row, {}, cache, parts, excluded, begin, finish, previous, _history=history
        )
        if item is None:
            continue
        identity = (item["game_key"], item["ply"], item["skill"], item["operation"], item["family"])
        if identity in seen:
            excluded["duplicate decision"] += 1
            continue
        inspected = source(
            db, learner, {"id": item["id"], "position_id": item["position_id"]}, _history=history
        )
        example = describe(inspected) if inspected else None
        if not example or not example["lines"]:
            excluded["lesson or legal line unavailable"] += 1
            continue
        seen.add(identity)
        key = (item["skill"], item["operation"], item["family"], item["version"])
        groups[key].append(item)
