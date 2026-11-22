"""Resolve a licensed, exact public mate prompt without running a solver."""

import chess

from .fact_fingerprint import canonical, digest
from .public_mate_contract import OBJECTIVE
from .public_training_source import resolve
from .tactical_exposure_practice import check as exposure
from .unified_source_current import snapshot_hash


def candidate(db, subject, version, key):
    snapshot = resolve(db, version, key, verify=False)
    if snapshot["objective"] != OBJECTIVE:
        return None, "unavailable"
    prompt = prompt_key(snapshot["prompt_fen"])
    history = exposure(db, subject, prompt)
    if history not in {"clear", "history_unknown"}:
        return None, "provided" if history == "provided" else "exposure_unknown"
    fingerprint = snapshot_hash(snapshot)
    binding = digest(canonical([version, key, fingerprint, prompt, history]))
    source = snapshot["provenance"]
    note = " Earlier coach delivery is unknown." if history == "history_unknown" else ""
    return {
        "kind": "new",
        "item_id": None,
        "due": None,
        "source_type": "public",
        "source_version": version,
        "source_key": key,
        "prompt_fen": snapshot["prompt_fen"],
        "prompt_key": prompt,
        "skill": "mate_in_one",
        "operation": "execute",
        "objective": "Find checkmate in one.",
        "reason": "Optional mate practice; this does not establish mastery." + note,
        "source_attribution": source["attribution"],
        "source_license": source["license"],
        "source_snapshot_hash": fingerprint,
        "exposure_state": history,
        "unified_training": True,
        "binding": binding,
    }, "available"


def rows(db, after, limit):
    return db.connection.execute(
        """SELECT c.id,c.version,t.task_id,substr(t.objective,1,257) AS objective
        FROM public_collections c JOIN public_tasks t ON t.collection_id=c.id
        WHERE c.state='ready' AND (c.id>? OR (c.id=? AND t.task_id>?))
        ORDER BY c.id,t.task_id LIMIT ?""",
        (after[0], after[0], after[1], limit + 1),
    ).fetchall()


def version(db, collection):
    row = db.connection.execute(
        "SELECT version FROM public_collections WHERE id=? AND state='ready'", (collection,)
    ).fetchone()
    return row[0] if row else None


def prompt_key(fen):
    return " ".join(chess.Board(fen).fen(en_passant="fen").split()[:4])
