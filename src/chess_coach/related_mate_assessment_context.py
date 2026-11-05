"""Freeze the content and matching context used at assessment admission."""

from .related_mate_features import corpus_features, mate_features

VERSION = "mate-assessment-context-v1"


def _features(row, source):
    _, content = corpus_features(row["fen"], row["solution"])
    original = mate_features(source["prompt_fen"], source["lines"][0].split())
    if not content or not original:
        raise ValueError("assessment context unavailable")
    return content, original


def _ratings(row):
    rating, deviation = row["rating"], row["rating_deviation"]
    if type(rating) is not int or type(deviation) is not int:
        raise ValueError("assessment context unavailable")
    return rating, deviation


def capture(db, version, key, source, baseline, corpus):
    row = db.connection.execute(
        """SELECT p.fen,p.solution,p.rating,p.rating_deviation,p.opening
        FROM puzzles p JOIN puzzle_corpora c ON c.id=p.corpus_id
        WHERE c.version=? AND c.state='ready' AND p.puzzle_id=?""",
        (version, key),
    ).fetchone()
    if row is None:
        raise ValueError("assessment content unavailable")
    content, original = _features(row, source)
    rating, deviation = _ratings(row)
    opening = row["opening"] or ""
    return {
        "version": VERSION,
        "corpus_checksum": corpus["checksum"],
        "content_rating": rating,
        "content_deviation": deviation,
        "mechanism": {key: content[key] for key in ("mover", "target", "timing", "geometry")},
        "source_mechanism": {
            key: original[key] for key in ("mover", "target", "timing", "geometry")
        },
        "content_phase": content["phase"],
        "source_phase": original["phase"],
        "same_phase": content["phase"] == original["phase"],
        "same_material": content["material"] == original["material"],
        "material_distance": sum(
            abs(a - b) for a, b in zip(content["material"], original["material"], strict=True)
        ),
        "same_opening": bool(source.get("opening") and source["opening"] in opening.split()),
        "ranking_baseline": baseline,
    }
