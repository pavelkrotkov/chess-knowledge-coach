"""Gate scores and find the played root in the same ranked search."""

MIN_DEPTH = 4


def score_ok(line):
    return (
        line.get("status") == "limited"
        and line.get("score_kind") == "cp"
        and line.get("score_bound") == "exact"
        and type(line.get("score_value")) is int
        and type(line.get("depth")) is int
        and line["depth"] >= MIN_DEPTH
    )


def chosen(lines, played):
    chosen = next((line for line in lines if line["root_move"] == played), None)
    if chosen is None:
        return None, "played_root_not_covered"
    if not score_ok(chosen):
        return None, "score_unusable"
    return chosen, None
