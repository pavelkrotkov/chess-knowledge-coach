"""Attach the bounded proof results without treating unknown as a choice."""

from .style_protection_snapshot import inspect


def annotate(db, learner, context, board, deep, compared, budget):
    budget["considered"] += 1
    previous_skips = budget["skipped"]
    results = inspect(db, learner, context, board, deep, compared, budget)
    if budget["skipped"] > previous_skips:
        budget["skipped_decisions"] += 1
    unknown = {"status": "unknown", "reason": "source_or_proof_unavailable"}
    if results is None:
        budget["unsupported"] += 1
        results = {}
    for pair in compared["pairs"]:
        pair["played"]["protection"] = results.get(compared["played"]["root_move"], unknown)
        pair["alternative"]["protection"] = results.get(
            pair["alternative_line"]["root_move"], unknown
        )
    if results and all(item["status"] == "supported" for item in results.values()):
        budget["completed"] += 1
    elif results:
        budget["unsupported"] += 1
