"""Classify independent selection nominations without inferring skills."""

CATEGORIES = ("score", "uncertain", "opportunity")


def categories(reasons):
    groups = set()
    if "cp_score_gap" in reasons or "wdl_score_gap" in reasons:
        groups.add("score")
    if {
        "mate_score",
        "bounded_score",
        "score_kind_mismatch",
        "score_inversion",
        "score_unavailable",
    }.intersection(reasons):
        groups.add("uncertain")
    if any(
        reason.startswith("possible_") or reason == "mate_in_one_available" for reason in reasons
    ):
        groups.add("opportunity")
    return groups
