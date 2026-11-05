"""Compare rebuilt chapter content and legal Study replay."""

import io

import chess.pgn

from .fact_fingerprint import canonical
from .study_pgn_verify import matches


def compare(saved, expected):
    if canonical(saved) != canonical(expected) or saved["mode"] != "conceal":
        raise ValueError("course chapter differs")
    game = chess.pgn.read_game(io.StringIO(saved["pgn"]))
    if game is None or game.errors:
        raise ValueError("course chapter is invalid")
    game.headers["ChapterName"] = saved["title"]
    game.headers["Orientation"] = saved["orientation"]
    if not matches({**expected, "name": saved["title"]}, str(game)):
        raise ValueError("course chapter replay differs")
