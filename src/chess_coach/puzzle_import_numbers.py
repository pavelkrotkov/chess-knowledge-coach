"""Parse and validate numeric corpus metadata."""


def parse_numbers(row: dict[str, str]):
    try:
        rating = int(row["Rating"])
        deviation = int(row["RatingDeviation"])
        popularity = _optional_int(row.get("Popularity"))
        plays = _optional_int(row.get("NbPlays"))
    except ValueError:
        raise ValueError("CSV record has invalid numeric fields") from None
    if rating < 0 or deviation < 0 or (plays is not None and plays < 0):
        raise ValueError("CSV record has invalid numeric fields")
    return rating, deviation, popularity, plays


def _optional_int(value: str | None) -> int | None:
    return int(value) if value and value.strip() else None
