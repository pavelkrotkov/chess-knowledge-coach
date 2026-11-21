"""Resolve bounded delivered chapter positions and artifact digests."""

from .fact_fingerprint import digest
from .tactical_exposure_pgn import positions as pgn_positions
from .tactical_exposure_positions import MAX_CHAPTERS, line_positions


def entries(chapters, line):
    if not 1 <= len(chapters) <= MAX_CHAPTERS:
        raise ValueError("tactical material exceeds exposure limit")
    for index, chapter in chapters:
        pgn = chapter["pgn"]
        keys = pgn_positions(pgn) if line is None else line_positions(chapter, line)
        yield index, digest(pgn), keys
