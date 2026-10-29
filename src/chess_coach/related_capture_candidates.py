"""Retrieve bounded candidates through existing corpus and public indexes."""

import json
from urllib.parse import urlparse

from .related_capture_public import public_candidates


def candidates(db, version, rating, familiar_games, *, theme="hangingPiece", all_lines=False):
    corpus = db.connection.execute(
        "SELECT c.id,c.checksum,i.selection_json FROM puzzle_corpora c LEFT JOIN puzzle_imports i ON i.corpus_id=c.id WHERE c.version=? AND c.state='ready'",
        (version,),
    ).fetchone()
    if corpus is None:
        return [], None
    lower, upper = (max(0, rating - 500), min(3999, rating + 500)) if rating else (600, 2200)
    rows = _corpus_rows(db, corpus["id"], lower, upper, theme)
    result = [
        _corpus(row, version) for row in rows if _game_id(row["source"]) not in familiar_games
    ]
    public, metadata = public_candidates(db, familiar_games, all_lines=all_lines)
    result.extend(public)
    return result, {
        "checksum": corpus["checksum"],
        "selection": json.loads(corpus["selection_json"]) if corpus["selection_json"] else None,
        "scanned": len(rows),
        "lower": lower,
        "upper": upper,
        "public": metadata,
    }


def _corpus_rows(db, corpus_id, lower, upper, theme):
    rows = []
    width = max(1, (upper - lower + 1) // 5)
    for index in range(5):
        start = lower + index * width
        stop = upper if index == 4 else start + width - 1
        rows.extend(
            db.connection.execute(
                """SELECT p.* FROM puzzle_themes t JOIN puzzles p ON p.corpus_id=t.corpus_id AND p.puzzle_id=t.puzzle_id
            WHERE t.corpus_id=? AND t.theme=? AND t.rating BETWEEN ? AND ?
            ORDER BY t.rating,t.puzzle_id LIMIT 100""",
                (corpus_id, theme, start, stop),
            ).fetchall()
        )
    return rows


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
