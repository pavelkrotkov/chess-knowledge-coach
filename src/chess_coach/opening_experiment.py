"""Qualify one current two-root opening experiment and its legal continuations."""

import chess

from .opening_experiment_line import pair

MAX_DISADVANTAGE = 50


def assess(decision, choice, result):
    if result.get("status") != "complete":
        return None, "unavailable"
    lines = {line["root_move"]: line for line in result["lines"]}
    played, alternative = lines.get(decision["played_uci"]), lines.get(choice["uci"])
    if played is None or alternative is None:
        return None, "unavailable"
    reason = _gap(played, alternative, result)
    if reason:
        return None, reason
    branches, reason = pair(chess.Board(decision["fen"]), played, alternative)
    if branches is None:
        return None, reason
    experiment = {**branches, "depth": played["depth"]}
    if result.get("policy") == "all-legal-roots-v2":
        reference = result["lines"][0]
        experiment["reference"] = {"uci": reference["root_move"], "score": reference["score_value"]}
    return experiment, None


def _gap(played, alternative, result):
    # The played-move gap and the all-root reference gap answer different questions.
    if alternative["score_value"] < played["score_value"] - MAX_DISADVANTAGE:
        return "score_gap"
    if (
        result.get("policy") == "all-legal-roots-v2"
        and alternative["score_value"] < result["lines"][0]["score_value"] - MAX_DISADVANTAGE
    ):
        return "reference_gap"
    return None


def qualified(decision, choice, result):
    return assess(decision, choice, result)[0]


def report(source, result):
    decision = {"fen": source["decision_fen"], "played_uci": source["played"]}
    _, reason = assess(decision, {"uci": source["alternative"]}, result)
    if result["status"] != "complete":
        return [f"Reference unavailable: {result.get('reason', 'unavailable')}."]
    lines = {line["root_move"]: line for line in result["lines"]}
    played, alternative = lines[source["played"]], lines[source["alternative"]]
    reference = result["lines"][0]
    details = {
        "reference_gap": "withheld: more than 50 cp below the best measured root",
        "score_gap": "withheld: more than 50 cp below the played move",
    }
    status = details.get(reason, f"withheld: {reason}" if reason else "within both 50 cp bounds")
    return [
        f"Alternative minus played: {alternative['score_value'] - played['score_value']} cp; "
        f"below best measured root: {reference['score_value'] - alternative['score_value']} cp.",
        f"Worked experiment: {status}.",
    ]
