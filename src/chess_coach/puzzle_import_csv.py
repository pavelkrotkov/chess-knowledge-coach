"""Read complete CSV records and validate chess lines at the real prompt."""

import csv
from pathlib import Path

import chess

from .puzzle_session_validate import validate_line

REQUIRED = {"PuzzleId", "FEN", "Moves", "Rating", "RatingDeviation"}


def _lines(stream):
    while line := stream.readline():
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
                rows.append(_row(dict(zip(fields, values, strict=True))))
                offset = stream.tell()
                if len(rows) == limit:
                    break
            return rows, offset, offset == path.stat().st_size
    except (csv.Error, UnicodeError):
        raise ValueError("malformed CSV record") from None


def _row(row: dict[str, str]) -> dict:
    if any(not row[key].strip() for key in REQUIRED):
        raise ValueError("CSV record is missing required fields")
    try:
        rating = int(row["Rating"])
        deviation = int(row["RatingDeviation"])
        popularity = _optional_int(row.get("Popularity"))
        plays = _optional_int(row.get("NbPlays"))
    except ValueError:
        raise ValueError("CSV record has invalid numeric fields") from None
    if rating < 0 or deviation < 0 or (plays is not None and plays < 0):
        raise ValueError("CSV record has invalid numeric fields")
    themes = sorted(set(row.get("Themes", "").split()))
    result = {
        "puzzle_id": row["PuzzleId"].strip(),
        "fen": row["FEN"].strip(),
        "solution": row["Moves"].strip(),
        "rating": rating,
        "deviation": deviation,
        "popularity": popularity,
        "play_count": plays,
        "themes": themes,
        "source": row.get("GameUrl", ""),
        "opening": row.get("OpeningTags") or None,
    }
    try:
        prompt = validate_line(result["fen"], result["solution"])
        board = chess.Board(prompt)
        result.update(
            prompt_fen=prompt,
            prompt_key=" ".join(prompt.split()[:4]),
            prompt_turn="white" if board.turn else "black",
            valid=True,
        )
    except ValueError:
        result["valid"] = False
    return result


def _optional_int(value: str | None) -> int | None:
    return int(value) if value and value.strip() else None
