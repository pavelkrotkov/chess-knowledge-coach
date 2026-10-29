"""Resolve ready corpus and licensed direct-prompt sources for practice."""

import chess

from .public_training_query import task as public_task
from .public_training_validate import validate_task
from .puzzle_session_validate import solution_moves, validate_line


def resolve_source(db, source_type, version, key):
    if source_type == "corpus":
        return _corpus(db, version, key)
    if source_type == "public":
        return _public(db, version, key)
    raise ValueError("unsupported practice source")


def _corpus(db, version, key):
    row = db.connection.execute(
        """SELECT p.fen,p.solution,c.checksum FROM puzzles p
        JOIN puzzle_corpora c ON c.id=p.corpus_id WHERE c.version=? AND p.puzzle_id=?
        AND c.state IN (\u0027ready\u0027,\u0027legacy_ready\u0027)""",
        (version, key),
    ).fetchone()
    if row is None:
        raise ValueError("practice source is unavailable")
    moves = solution_moves(row["solution"])
    if len(moves) > 65:
        raise ValueError("practice line exceeds the supported bound")
    prompt = validate_line(row["fen"], row["solution"])
    line = " ".join(moves[1:])
    return _snapshot(prompt, "legal_line", [line], {"corpus_checksum": row["checksum"]})


def _public(db, version, key):
    row = public_task(db, version, key)
    if row is None:
        raise ValueError("practice source is unavailable")
    candidate = validate_task(
        {"id": key, "fen": row["prompt_fen"], "objective": row["objective"], "lines": row["lines"]}
    )
    fields = (
        "source_url",
        "source_revision",
        "source_sha256",
        "content_sha256",
        "license",
        "attribution",
        "license_notice",
    )
    provenance = {field: row[field] for field in fields}
    return _snapshot(candidate["fen"], candidate["objective"], candidate["lines"], provenance)


def _snapshot(prompt, objective, lines, provenance):
    board = chess.Board(prompt)
    return {
        "prompt_fen": board.fen(),
        "learner_color": "white" if board.turn else "black",
        "objective": objective,
        "lines": lines,
        "provenance": provenance,
    }
