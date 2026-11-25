"""Bind one admitted learner choice to current revision evidence."""

VERSION = "opening-recommendation-v1"


def _chosen(judgments, move):
    choices = [row for row in judgments["alternatives"] if row["choice"]["uci"] == move]
    if len(choices) != 1 or choices[0]["admission"]["status"] != "eligible":
        raise ValueError("selected alternative is unavailable or excluded")
    return choices[0]


def selection(report, game_id, position_id, move):
    branch = report.get("branch")
    judgments = report.get("revision_judgments", {})
    if branch is None or judgments.get("status") != "checked":
        raise ValueError("current recommendation unavailable")
    exemplar = branch["exemplar"]
    if (exemplar["game_id"], exemplar["position_id"]) != (game_id, position_id):
        raise ValueError("opening recommendation changed")
    selected = _chosen(judgments, move)
    if not (judgments["fit"]["eligible"] or judgments["development"]["eligible"]):
        raise ValueError("no supported recommendation evidence")
    return selected


def rationale_snapshot(report, move, state_hash):
    return {
        "version": VERSION,
        "branch": report["branch"],
        "nomination": report["fork_nomination"],
        "judgments": report["revision_judgments"],
        "sample": report["coverage"],
        "partial": report["partial"],
        "selected": move,
        "input_state_sha256": state_hash,
    }
