"""Retrieve bounded candidates through existing corpus and public indexes."""

import json
from urllib.parse import urlparse

from .related_capture_public import public_candidates
from .related_corpus_window import corpus_rows


def candidates(
    db,
    version,
    rating,
    familiar_games,
    *,
    theme="hangingPiece",
    all_lines=False,
    include_objective=False,
    per_band=100,
):
    corpus = db.connection.execute(
        "SELECT c.id,c.checksum,i.selection_json FROM puzzle_corpora c LEFT JOIN puzzle_imports i ON i.corpus_id=c.id WHERE c.version=? AND c.state='ready'",
        (version,),
    ).fetchone()
    if corpus is None:
        return [], None
    lower, upper = (max(0, rating - 500), min(3999, rating + 500)) if rating else (600, 2200)
    rows, limited = corpus_rows(db, corpus["id"], lower, upper, theme, per_band)
    result = [
        _corpus(row, version) for row in rows if _game_id(row["source"]) not in familiar_games
    ]
    public, public_metadata = public_candidates(
        db, familiar_games, all_lines=all_lines, include_objective=include_objective
    )
    result.extend(public)
    metadata = {
        "checksum": corpus["checksum"],
        "selection": json.loads(corpus["selection_json"]) if corpus["selection_json"] else None,
        "scanned": len(rows),
        "lower": lower,
        "upper": upper,
        "public": public_metadata,
    }
    if per_band != 100:
        metadata["limited"] = limited
    return result, metadata


def _game_id(source):
    parsed = urlparse(source)
    if parsed.hostname not in {"lichess.org", "www.lichess.org"}:
        return None
    return parsed.path.strip("/").split("/")[0]


def _corpus(row, version):
    return {
        "type": "corpus",
        "version": version,
        "key": row["puzzle_id"],
        "fen": row["fen"],
        "solution": row["solution"],
        "game": _game_id(row["source"]),
        "opening": row["opening"],
        "rating": row["rating"],
        "rating_deviation": row["rating_deviation"],
    }
