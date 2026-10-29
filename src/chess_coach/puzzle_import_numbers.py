"""Parse and validate numeric corpus metadata."""


def parse_numbers(row: dict[str, str]):
    try:
        rating = int(row["Rating"])
        deviation = int(row["RatingDeviation"])
        popularity = _optional_int(row.get("Popularity"))
        plays = _optional_int(row.get("NbPlays"))
    except ValueError:
        raise ValueError("CSV record has invalid numeric fields") from None
    _validate_ranges(rating, deviation, popularity, plays)
    return rating, deviation, popularity, plays


def _optional_int(value: str | None) -> int | None:
    return int(value) if value and value.strip() else None


def _validate_ranges(
    rating: int, deviation: int, popularity: int | None, plays: int | None
) -> None:
    maximum = 2**63 - 1
    if not (0 <= rating <= maximum and 0 <= deviation <= maximum):
        raise ValueError("CSV record has invalid numeric fields")
    if plays is not None and not 0 <= plays <= maximum:
        raise ValueError("CSV record has invalid numeric fields")
    if popularity is not None and not -100 <= popularity <= 100:
        raise ValueError("CSV record has invalid numeric fields")
