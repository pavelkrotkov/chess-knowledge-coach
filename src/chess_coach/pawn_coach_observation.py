"""Extract verified choices from a history-aware pawn proof."""

from .pawn_coach_classify import classify, root_value


def observe(proof, played):
    root, preserving, worse, chosen = _choices(proof, played)
    outcome, reason = classify(root, preserving, worse, chosen)
    return {
        "kind": "pawn_endgame",
        "outcome": outcome,
        "reason": reason,
        "root_wdl": root,
        "played_uci": played,
        "preserving": preserving,
        "worse": worse,
        "proof": proof,
    }


def _choices(proof, played):
    alternatives = proof.get("alternatives", [])
    root = root_value(proof)
    exact = [item for item in alternatives if item["lower"] == item["upper"]]
    preserving, worse = _partition(exact, root)
    chosen = next((item for item in exact if item["move"]["uci"] == played), None)
    return root, preserving, worse, chosen


def _partition(exact, root):
    if root is None:
        return [], []
    return (
        [item["move"] for item in exact if item["lower"] == root],
        [item["move"] for item in exact if item["upper"] < root],
    )
