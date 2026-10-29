"""Parse source metadata and derive a legally validated learner prompt."""

from .puzzle_import_numbers import parse_numbers
from .puzzle_import_prompt import attach_prompt

REQUIRED = {"PuzzleId", "FEN", "Moves", "Rating", "RatingDeviation"}


def parse_record(row: dict[str, str]) -> dict:
    if any(not row[key].strip() for key in REQUIRED):
        raise ValueError("CSV record is missing required fields")
    rating, deviation, popularity, plays = parse_numbers(row)
    themes = _themes(row)
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
    attach_prompt(result)
    return result


def _themes(row: dict[str, str]) -> list[str]:
    themes = sorted(set(row.get("Themes", "").split()))
    if len(row["PuzzleId"].strip()) > 256 or len(themes) > 64 or any(len(t) > 64 for t in themes):
        raise ValueError("CSV record exceeds identifier or theme bounds")
    return themes
