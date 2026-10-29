"""Use a cheap mate score as a nomination, never as proof or a negative claim."""


def short_candidate(snapshot, position_id):
    return any(_candidate(line, position_id) for line in snapshot["lines"])


def _candidate(line, position_id):
    value = line["score_value"]
    return (
        line["position_id"] == position_id
        and line["role"] == "best"
        and line["score_kind"] == "mate"
        and value is not None
        and 0 < value <= 2
    )
