"""Describe a bounded comparison separately from the playable public line."""


def describe(value):
    played, other = value["played"], value["other"]
    short = min(len(played["san"]), len(other["san"])) < 3
    scope = (
        "At least one returned variation is shorter than three plies, so a worked engine "
        "continuation is unavailable. "
        if short
        else ""
    )
    source = (
        "This comparison comes from an earlier game you played. " if value.get("decision") else ""
    )
    return (
        source
        + f"Current same-search comparison at depth {played['depth']} with {value['nodes']} nodes, "
        "in centipawns from your "
        f"side: the played move {played['san'][0]} scored {played['score']} cp "
        f"({', '.join(played['san'])}); the selected move {other['san'][0]} scored "
        f"{other['score']} cp ({', '.join(other['san'])}). "
        f"These are bounded estimates for these two roots. {scope}"
        "The playable continuation comes from the licensed public game."
    )


def tree(item, parent):
    branches = (
        "; ".join(
            " ".join(other["source"]["line"]["san"])
            for other in parent["items"]
            if other["source"] is not None
        )
        or "unavailable"
    )
    distance = item["distance"]
    counts = distance.get("counts")
    if not counts:
        return f"Recorded public branches: {branches}. The wider response tree remains unknown. "
    new = counts.get("new_positions")
    not_seen = "unknown" if new is None else str(new)
    return (
        f"Recorded public branches: {branches}. The checked sample has "
        f"{distance['branches']} distinct branches, {counts['responses']} responses and "
        f"{distance['transpositions']} transpositions; positions not seen in checked history: "
        f"{not_seen}. "
    )
