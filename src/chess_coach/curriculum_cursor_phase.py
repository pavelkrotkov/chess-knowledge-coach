"""Check consistency between continuation scan phases."""


def validate_phase(state: dict) -> None:
    if len(state["seen"]) >= state["limit"]:
        raise ValueError("completed plans cannot continue")
    if state["phase"] == "due" and (state["new_after"] is not None or state["pending"] is not None):
        raise ValueError("due scan cannot contain a corpus position")
    pending, prior = state["pending"], state["new_after"]
    if pending is not None and prior is not None and pending[:2] <= prior:
        raise ValueError("pending candidate does not follow the corpus position")
