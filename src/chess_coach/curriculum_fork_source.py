"""Resolve one qualified owned fork under the plan deadline."""

import chess

from .fact_fingerprint import canonical, digest
from .fork_plan_action import checked
from .objective_contract import OWNED_HISTORY
from .objective_fork_contract import GOAL, MISS_OBJECTIVE, MISS_VERSION
from .objective_fork_source import resolve
from .unified_source_current import snapshot_hash


def read(db, subject, corpus, check, *, include_snapshot=False):
    report = checked(db, subject, corpus, check)
    if not report:
        return None, "no_source", None
    source = report["source"]
    if not _source_valid(source):
        raise ValueError("fork source unavailable")
    # Resolve the exact owner-bound objective again; the lesson itself is advisory.
    snapshot = resolve(db, MISS_VERSION, source["key"], subject, check=check)
    if not _snapshot_valid(snapshot, source["evidence_id"]):
        raise ValueError("fork objective unavailable")
    check()
    if include_snapshot:
        report = {**report, "snapshot": snapshot}
    return _candidate(report, snapshot), "available", report


def _source_valid(source):
    return (
        source["version"] == MISS_VERSION
        and source["kind"] == "fork"
        and source["key"] == str(source["evidence_id"])
    )


def _snapshot_valid(snapshot, evidence_id):
    provenance = snapshot["provenance"]
    return (
        snapshot["objective"] == GOAL
        and provenance["objective_version"] == MISS_OBJECTIVE
        and provenance["history_mode"] == OWNED_HISTORY
        and provenance["evidence_id"] == evidence_id
    )


def _candidate(report, snapshot):
    source, provenance = report["source"], snapshot["provenance"]
    board = chess.Board(snapshot["prompt_fen"])
    coverage = "bounded recent observations" + ("; more may exist" if report["limited"] else "")
    reason = (
        f"Provisional diagnostic from {report['games']} independent games ({coverage}); "
        f"source review: {provenance['review_status']}; "
        f"recent assessment: {report['assessment']['status']}. "
        + (
            "A harder assessment band is supported. "
            if report["harder"]
            else "A harder assessment band is not established. "
        )
        + "The bounded fork proof does not establish mastery."
    )
    return {
        "kind": "new",
        "item_id": None,
        "due": None,
        "source_type": "own-game",
        "source_version": MISS_VERSION,
        "source_key": str(source["evidence_id"]),
        "source_evidence_id": source["evidence_id"],
        "source_review": provenance["review_status"],
        "independent_games": report["games"],
        "prompt_fen": snapshot["prompt_fen"],
        "prompt_key": " ".join(board.fen(en_passant="fen").split()[:4]),
        "skill": "fork",
        "operation": "execute",
        "objective": f"Move the piece on {provenance['fork_attacker']} to fork the piece on {provenance['fork_anchor']}.",
        "reason": reason,
        "unified_training": True,
        "binding": digest(
            canonical([source["evidence_id"], snapshot_hash(snapshot), report["assessment"]])
        ),
    }
