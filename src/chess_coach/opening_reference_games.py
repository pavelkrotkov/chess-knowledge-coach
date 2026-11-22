"""Collect a bounded sample of complete public reference games."""

import io

from .opening_reference_admit import admit as _admit
from .opening_reference_game import record as parse_record
from .opening_reference_visitor import read_game

MAX_RECORDS = 5000
MAX_GAMES = 1000


def collect(text, truncated, *, parser=None, check=None):
    if parser is None:
        parser = parse_record
    stream = io.StringIO(text)
    records, seen, urls = [], set(), set()
    counts = {"examined": 0, "excluded": 0, "duplicates": 0, "unknown_context": 0}
    while counts["examined"] < MAX_RECORDS and len(records) < MAX_GAMES:
        start = stream.tell()
        game = read_game(stream, check)
        if game is None:
            break
        raw = text[start : stream.tell()]
        counts["examined"] += 1
        record = parser(game, raw, counts["examined"])
        _admit(record, records, counts, seen, urls)
    counts["accepted"] = len(records)
    counts["truncated"] = truncated or stream.tell() < len(text)
    return records, counts
