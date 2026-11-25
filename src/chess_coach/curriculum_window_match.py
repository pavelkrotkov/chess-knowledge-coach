"""Match goals only to the source families they actually prioritize."""

SKILLS = {
    "capture": "hanging_piece",
    "fork": "fork",
    "mate": "mate_in_one",
    "promotion": "promotion",
}


def matches(item, goal):
    return (
        item["kind"] == "new"
        and item["skill"] == SKILLS[goal]
        and (goal != "mate" or item.get("source_type") == "public")
    )
