"""Validate complete standard broadcast PGN input."""

import re

import chess

from .public_training_pgn_lex import valid_movetext

RESULT = re.compile(r"(?:1-0|0-1|1/2-1/2)\s*$")


def valid(game, raw):
    result = game.headers.get("Result")
    return (
        not game.errors
        and valid_movetext(raw)
        and RESULT.search(raw)
        and game.headers.get("Variant", "Standard") in ("Standard", "Chess")
        and game.board().fen() == chess.Board().fen()
        and result in ("1-0", "0-1", "1/2-1/2")
        and raw.rstrip().endswith(result)
    )
