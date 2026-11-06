"""Collect a bounded sample of complete public reference games."""

import io

import chess.pgn

from .opening_reference_admit import admit as _admit
from .opening_reference_game import record as parse_record
from .public_training_pgn import QuietBuilder

MAX_RECORDS = 5000
MAX_GAMES = 1000


def collect(text, truncated):
    stream = io.StringIO(text)
    records, seen, urls = [], set(), set()
    counts = {"examined": 0, "excluded": 0, "duplicates": 0, "unknown_context": 0}
    while counts["examined"] < MAX_RECORDS and len(records) < MAX_GAMES:
        start = stream.tell()
        game = chess.pgn.read_game(stream, Visitor=QuietBuilder)
        if game is None:
            break
        raw = text[start : stream.tell()]
        counts["examined"] += 1
        record = parse_record(game, raw, counts["examined"])
        _admit(record, records, counts, seen, urls)
    counts["accepted"] = len(records)
    counts["truncated"] = truncated or stream.tell() < len(text)
    return records, counts
