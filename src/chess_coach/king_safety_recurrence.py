"""Validate descriptive king-safety recurrence mappings."""


def king_ok(row, fact):
    return (
        (row["skill"], row["operation"], row["outcome"]) == ("king_safety", "evaluate", "ambiguous")
        and fact["payload"].get("version") == "1.0.0"
        and fact["payload"].get("mastery_eligible") is False
    )
