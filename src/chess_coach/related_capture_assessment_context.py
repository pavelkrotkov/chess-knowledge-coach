"""Freeze the content and matching context at capture assessment admission."""

from .related_capture_features import capture_features, corpus_features

VERSION = "capture-assessment-context-v1"


def _ratings(row):
    rating, deviation = row["rating"], row["rating_deviation"]
    if type(rating) is not int or type(deviation) is not int or rating < 0 or deviation < 0:
        raise ValueError("assessment context unavailable")
    return rating, deviation


def _same_opening(source, opening):
    return bool(source.get("opening") and source["opening"] in (opening or "").split())


def capture(db, version, key, source, baseline, corpus):
    row = db.connection.execute(
        """SELECT p.fen,p.solution,p.rating,p.rating_deviation,p.opening FROM puzzles p
        JOIN puzzle_corpora c ON c.id=p.corpus_id
        WHERE c.version=? AND c.state='ready' AND p.puzzle_id=?""",
        (version, key),
    ).fetchone()
    if row is None:
        raise ValueError("assessment context unavailable")
    rating, deviation = _ratings(row)
    _, content = corpus_features(row["fen"], row["solution"])
    original = capture_features(source["prompt_fen"], source["lines"][0].split())
    if not content or not original:
        raise ValueError("assessment context unavailable")
    return {
        "version": VERSION,
        "corpus_checksum": corpus["checksum"],
        "content_rating": rating,
        "content_deviation": deviation,
        "mechanism": {key: content[key] for key in ("mover", "target", "geometry")},
        "source_mechanism": {key: original[key] for key in ("mover", "target", "geometry")},
        "content_phase": content["phase"],
        "source_phase": original["phase"],
        "same_phase": content["phase"] == original["phase"],
        "same_geometry": content["geometry"] == original["geometry"],
        "same_opening": _same_opening(source, row["opening"]),
        "same_material": content["material"] == original["material"],
        "material_distance": sum(
            abs(a - b) for a, b in zip(content["material"], original["material"], strict=True)
        ),
        "ranking_baseline": baseline,
    }
