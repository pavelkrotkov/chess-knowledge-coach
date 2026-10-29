"""Keep king-safety sources closed until independent qualification."""


def closed(row):
    return (
        row["skill"] == "king_safety"
        or row["mapping_producer"] == "king-safety-lesson-mapper"
        or row["king_safety_fact_count"]
    )
