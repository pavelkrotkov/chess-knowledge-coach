"""Conservatively identify known learner and legacy practice positions."""

import io

import chess
import chess.pgn

from .learner_identity import normalize_identity
from .puzzle_session_validate import validate_line
from .related_capture_position import prompt_key
from .related_capture_probe import position_probe

LIMIT = 200000


def familiarity(db, subject, *, check=lambda: None):
    identity = normalize_identity(subject)
    if not identity:
        raise ValueError("practice subject unavailable")
    games = db.connection.execute(
        "SELECT source_id,pgn FROM games WHERE lower(white)=? OR lower(black)=? LIMIT 200001",
        (identity, identity),
    ).fetchall()
    if len(games) > LIMIT:
        raise ValueError("familiarity scan limit exceeded")
    prompts = _legacy_sessions(db, check=check)
    for row in games:
        check()
        prompts.add(_initial_prompt(row["pgn"]))
    ids = {row["source_id"] for row in games if row["source_id"]}
    return prompts, ids, position_probe(db, identity, subject)


def _initial_prompt(pgn):
    headers = chess.pgn.read_headers(io.StringIO(pgn))
    if headers is None:
        raise ValueError("familiarity source unavailable")
    try:
        return prompt_key(headers.board().fen())
    except ValueError:
        raise ValueError("familiarity source unavailable") from None


def _legacy_sessions(db, *, check=lambda: None):
    legacy = db.connection.execute(
        "SELECT initial_fen,solution FROM puzzle_sessions LIMIT 200001"
    ).fetchall()
    if len(legacy) > LIMIT:
        raise ValueError("familiarity scan limit exceeded")
    prompts = set()
    for row in legacy:
        check()
        prompts.add(prompt_key(validate_line(row["initial_fen"], row["solution"])))
    return prompts
