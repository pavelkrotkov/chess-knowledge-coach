"""Select one licensed, bounded defensive-themed worked corpus line."""

import chess

from .course_guidance import thematic_note
from .course_pgn import chapter
from .related_capture_source import baseline
from .related_corpus_window import corpus_rows
from .tactical_course_protection import PER_BAND
from .tactical_course_related import PROTECTION_EMPTY, PROTECTION_SOURCE
from .tactical_course_thematic_corpus import licensed
from .tactical_course_thematic_exposure import candidate
from .unified_sources import resolve_source

VERSION = "defensive-thematic-worked-v1"


def fallback(db, subject, corpus, choice, familiar_data, result, *, artifact=None):
    if result[0] is not None or result[1] not in {PROTECTION_EMPTY, PROTECTION_SOURCE}:
        return result
    metadata = licensed(db, corpus)
    if metadata is None:
        return result
    own = resolve_source(db, "own-game", choice["version"], choice["key"], subject=subject)
    rating = baseline(db, own)
    lower, upper = (max(0, rating - 500), min(3999, rating + 500)) if rating else (600, 2200)
    rows, limited = corpus_rows(db, metadata["id"], lower, upper, "defensiveMove", PER_BAND)
    for row in rows:
        found = candidate(db, subject, corpus, row, own, familiar_data, artifact)
        if found is None:
            continue
        snapshot, exposure = found
        if snapshot["provenance"]["corpus_checksum"] != metadata["checksum"]:
            raise ValueError("thematic corpus changed")
        board = chess.Board(snapshot["prompt_fen"])
        first = board.san(board.parse_uci(snapshot["lines"][0].split()[0]))
        note = thematic_note(row["rating"], lower, upper, limited, exposure, first)
        provenance = {
            "type": "corpus",
            "version": corpus,
            "key": row["puzzle_id"],
            "binding": {"version": VERSION, "evidence_id": choice["evidence_id"]},
        }
        return chapter("Thematic defensive practice", note, snapshot, provenance), None
    return result
