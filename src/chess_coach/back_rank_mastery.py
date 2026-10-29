"""Keep every back-rank family source ineligible pending qualification."""


def closed(row):
    return (
        row["skill"] == "back_rank"
        or row["mapping_producer"] == "back-rank-observation-mapper"
        or row["back_rank_fact_count"]
    )
