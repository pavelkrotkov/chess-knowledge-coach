"""Record and recheck real fork assessment rating inputs."""

from .capture_compare_rules import ratings
from .common_practice_ratings import read as rating_inputs

VERSION = "fork-common-controls-v1"


def record(db, selection, version, key, difficulty):
    row = db.connection.execute(
        """SELECT p.rating,p.rating_deviation FROM puzzles p JOIN puzzle_corpora c
        ON c.id=p.corpus_id WHERE c.version=? AND c.state='ready' AND p.puzzle_id=?""",
        (version, key),
    ).fetchone()
    if row is None:
        raise ValueError("fork control source unavailable")
    result = {
        "version": VERSION,
        "baseline": selection[1],
        "rating": row["rating"],
        "deviation": row["rating_deviation"],
        "admission": "harder" if difficulty is not None else "ordinary",
    }
    if difficulty is not None:
        result["lineage"] = dict(difficulty)
    return result


def current(db, row, binding, side):
    saved = binding["assessment"].get("common_controls")
    if not isinstance(saved, dict) or saved.get("version") != VERSION:
        return None
    values = (saved.get("baseline"), saved.get("rating"), saved.get("deviation"))
    context = {
        "ranking_baseline": values[0],
        "content_rating": values[1],
        "content_deviation": values[2],
    }
    if not ratings(context) or values[0] is None:
        return None
    if saved.get("admission") not in {"ordinary", "harder"}:
        return None
    actual = rating_inputs(
        db, row["source_version"], row["source_key"], binding["position_id"], side
    )
    return saved if actual is not None and actual[:3] == values else None
