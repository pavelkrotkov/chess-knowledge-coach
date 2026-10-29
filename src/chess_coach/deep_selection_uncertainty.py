"""Name unresolved engine score conditions without inferring a skill."""


def uncertainty_reasons(best, played):
    reasons = set()
    if best["score_kind"] == "mate" or played["score_kind"] == "mate":
        reasons.add("mate_score")
    if best["score_bound"] != "exact" or played["score_bound"] != "exact":
        reasons.add("bounded_score")
    if best["score_kind"] != played["score_kind"]:
        reasons.add("score_kind_mismatch")
    return reasons
