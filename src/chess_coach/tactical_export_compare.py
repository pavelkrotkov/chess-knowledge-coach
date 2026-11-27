"""Compare rebuilt chapter content and legal Study replay."""

import io

import chess.pgn

from .fact_fingerprint import canonical
from .study_pgn_verify import matches


def compare(saved, expected, *, gamebook=False, roles=False):
    if expected is None:
        raise ValueError("related source unavailable")
    if roles:
        expected = {**expected, "role": "practice"}
    modes = {"conceal", "gamebook"} if gamebook else {"conceal"}
    if canonical(saved) != canonical(expected) or saved["mode"] not in modes:
        raise ValueError("course chapter differs")
    game = chess.pgn.read_game(io.StringIO(saved["pgn"]))
    if game is None:
        raise ValueError("course chapter is invalid")
    game.headers["ChapterName"] = saved["title"]
    game.headers["Orientation"] = saved["orientation"]
    if not matches({**expected, "name": saved["title"]}, str(game)):
        raise ValueError("course chapter replay differs")
