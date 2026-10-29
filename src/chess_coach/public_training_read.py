"""Read bounded direct-FEN CSV or PGN task candidates."""

import csv
import json

from .public_training_pgn import read_pgn


def candidates(path, content_format):
    if content_format == "fen_csv":
        yield from _csv(path)
    else:
        yield from read_pgn(path)


def _csv(path):
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if reader.fieldnames != ["id", "fen", "objective", "lines"]:
            raise ValueError("invalid FEN collection header")
        for number, row in enumerate(reader, 1):
            if number > 5000:
                raise ValueError("collection record limit exceeded")
            try:
                lines = json.loads(row["lines"])
                yield number, {**row, "lines": lines}, None
            except (TypeError, json.JSONDecodeError):
                yield number, None, "invalid solution lines"
