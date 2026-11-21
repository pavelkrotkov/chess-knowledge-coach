"""Count retained games with known, excluded or incomplete nominal context."""


def context_coverage(records):
    counts = {
        "known_nominal_context": 0,
        "unknown_nominal_context": 0,
        "excluded_nominal_context": 0,
    }
    ratings = []
    for record in records:
        value = record[2]
        ratings.extend(filter(None, (value.get("WhiteElo"), value.get("BlackElo"))))
        if value.get("rated") is False or value.get("berserk") == "yes":
            counts["excluded_nominal_context"] += 1
        elif all(
            (
                value.get("TimeControl"),
                value.get("WhiteElo"),
                value.get("BlackElo"),
                value.get("rated"),
                value.get("Date") != "?",
            )
        ):
            counts["known_nominal_context"] += 1
        else:
            counts["unknown_nominal_context"] += 1
    counts["source_rating_min"] = min(ratings) if ratings else None
    counts["source_rating_max"] = max(ratings) if ratings else None
    counts["source_rating_labels"] = len(ratings)
    return counts
