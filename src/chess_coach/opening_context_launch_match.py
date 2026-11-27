"""Find the same-side reviewed fork within an ordinary plan page."""


def eligible(current, items):
    if current["admission"] != "development":
        return None
    owned = current["parent"]["development"]["owned"]["observations"]
    identifiers = {item["evidence_id"] for item in owned}
    for item in items:
        if (
            item["kind"] == "new"
            and item.get("source_type") == "own-game"
            and item["skill"] == "fork"
            and item.get("source_evidence_id") in identifiers
        ):
            return item
    return None
