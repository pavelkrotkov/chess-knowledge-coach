"""Keep source facts stable without hashing a new read timestamp."""

VERSION = "opening-recommendation-v1"


def _observation(item):
    decision = dict(item["decision"])
    decision.pop("processed_at", None)
    return {**item, "decision": decision}


def _nomination(value):
    return {**value, "observations": [_observation(item) for item in value["observations"]]}


def rationale_snapshot(report, move, state_hash):
    return {
        "version": VERSION,
        "branch": report["branch"],
        "nomination": _nomination(report["fork_nomination"]),
        "judgments": report["revision_judgments"],
        "sample": report["coverage"],
        "partial": report["partial"],
        "selected": move,
        "input_state_sha256": state_hash,
    }
