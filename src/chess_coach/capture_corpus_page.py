"""Walk actual indexed rows and overflow boundaries of one corpus window."""

from .capture_corpus_coverage import bind
from .related_corpus_window import band


def _next_row(db, building, check):
    _, _, lower, upper = building["scope"]
    while building["band"] < 5:
        check()
        start, stop = band(lower, upper, building["band"])
        last = building["last"] or [start - 1, ""]
        row = db.connection.execute(
            """SELECT p.*,t.rating AS indexed_rating FROM puzzle_themes t INDEXED BY idx_puzzle_themes_search
            JOIN puzzles p ON p.corpus_id=t.corpus_id AND p.puzzle_id=t.puzzle_id
            WHERE t.corpus_id=? AND t.theme=? AND t.rating BETWEEN ? AND ?
            AND (t.rating,t.puzzle_id)>(?,?) ORDER BY t.rating,t.puzzle_id LIMIT 1""",
            (building["corpus_id"], "hangingPiece", start, stop, *last),
        ).fetchone()
        if row is not None and building["count"] < 100:
            building["last"] = [row["indexed_rating"], row["puzzle_id"]]
            building["count"] += 1
            return row, False
        building.update(band=building["band"] + 1, last=None, count=0)
        if row is not None:
            building["limited"] = True
            return None, True
    return None, False


def discover(db, data, building, check):
    row, overflow = _next_row(db, building, check)
    if row is None:
        return overflow
    version, checksum, _, _ = building["scope"]
    key, candidate = bind(row, version, checksum)
    stage(data, building, building["keys"], key, candidate)
    return True


def stage(data, building, keys, key, candidate):
    keys.append(key)
    if key not in data["entries"]:
        data["prior"]["entries"][key] = {
            "identity": key,
            "state": "feature",
            "candidate": candidate,
        }
        building["pending"].append(key)
