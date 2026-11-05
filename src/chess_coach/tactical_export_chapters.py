"""Rebuild and compare the exact source-linked worked chapters."""

import io

import chess.pgn

from .fact_fingerprint import canonical
from .study_pgn_verify import matches
from .tactical_course_chapters import challenge, owned_chapter
from .tactical_course_related import unfamiliar
from .tactical_export_sources import choice


def _compare(saved, expected):
    if canonical(saved) != canonical(expected) or saved["mode"] != "conceal":
        raise ValueError("course chapter differs")
    game = chess.pgn.read_game(io.StringIO(saved["pgn"]))
    if game is None or game.errors:
        raise ValueError("course chapter is invalid")
    game.headers["ChapterName"] = saved["title"]
    game.headers["Orientation"] = saved["orientation"]
    if not matches({**expected, "name": saved["title"]}, str(game)):
        raise ValueError("course chapter replay differs")


def verify(db, subject, corpus, pattern, lesson, chapters, budget):
    selected = choice(db, subject, lesson, budget)
    if selected["kind"] != pattern["kind"] or pattern["local_challenge"] != challenge(selected):
        raise ValueError("selected source differs")
    with budget.scope(snapshot=True):
        owned = owned_chapter(
            db, subject, {"lesson": lesson}, selected, pattern["supporting_sources"]
        )
    with budget.scope(snapshot=False):
        _compare(chapters[0], owned)
    if len(chapters) == 2:
        with budget.scope(snapshot=False):
            related = unfamiliar(db, subject, corpus, selected)
            if related is None:
                raise ValueError("related source unavailable")
            _compare(chapters[1], related)
