"""Read complete CSV records and validate chess lines at the real prompt."""

import csv
from pathlib import Path

from .puzzle_import_record import REQUIRED, parse_record


def _lines(stream):
    while line := stream.readline(1_048_577):
        if len(line) > 1_048_576:
            raise ValueError("CSV line exceeds the import bound")
        yield line.decode("utf-8")


def header(path: Path) -> tuple[list[str], int]:
    try:
        with path.open("rb") as stream:
            fields = next(csv.reader(_lines(stream), strict=True))
            if len(fields) != len(set(fields)) or not REQUIRED.issubset(fields):
                raise ValueError("CSV header is missing or duplicated")
            return fields, stream.tell()
    except (StopIteration, csv.Error, UnicodeError):
        raise ValueError("invalid CSV header") from None


def read_batch(path: Path, offset: int, fields: list[str], limit: int):
    rows = []
    try:
        with path.open("rb") as stream:
            stream.seek(offset)
            reader = csv.reader(_lines(stream), strict=True)
            for values in reader:
                if len(values) != len(fields):
                    raise ValueError("CSV record has missing or extra fields")
                rows.append(parse_record(dict(zip(fields, values, strict=True))))
                offset = stream.tell()
                if len(rows) == limit:
                    break
            return rows, offset, offset == path.stat().st_size
    except (csv.Error, UnicodeError):
        raise ValueError("malformed CSV record") from None
