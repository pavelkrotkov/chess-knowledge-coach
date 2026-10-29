"""Classify a meaningful proved endgame choice without inferring intent."""


def classify(root, preserving, worse, chosen):
    if root not in (0, 1):
        return "ambiguous", "root_unknown_or_forced_loss"
    if not preserving or not worse:
        return "ambiguous", "no_verified_meaningful_choice"
    if chosen is None:
        return "ambiguous", "played_outcome_unknown"
    if chosen["lower"] == root:
        return "success", "outcome_preserved"
    if chosen["upper"] < root:
        return "failure", "outcome_lost"
    return "ambiguous", "played_outcome_unknown"


def root_value(proof):
    if proof.get("status") != "complete" or proof.get("lower") != proof.get("upper"):
        return None
    return proof.get("lower")
