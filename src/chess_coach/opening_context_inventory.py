"""Inventory a small, current set of exact unfamiliar opening contexts."""

import time

from .fact_fingerprint import canonical, digest
from .learner_identity import normalize_identity
from .opening_context_collect import collect
from .opening_context_history import sample
from .opening_context_owned_measure import MAX_GAMES as ANCHOR_GAMES
from .opening_public_proof_index import index_hash
from .opening_queue_budget import BrowserBudget
from .opening_snapshot import GRAPH_SHA256, SOURCE, VERSION
from .opening_unfamiliar_guard import check, start
from .opening_unfamiliar_sources import catalog_dataset
from .style_schedule_budget import LIMIT as HISTORY_LIMIT

SECONDS = 25


def inventory(db, root, learner, *, deadline=None, annotation=None):
    budget = BrowserBudget(db)
    budget.expires = min(budget.expires, time.monotonic() + SECONDS)
    if deadline is not None:
        budget.expires = min(budget.expires, deadline)
    subject = normalize_identity(learner)
    if subject is None:
        raise ValueError("learner unavailable")
    db.connection.create_function(
        "normalized_opening_owner", 1, normalize_identity, deterministic=True
    )
    try:
        binding = start(db, root, subject)
    except (OSError, ValueError):
        return {"status": "unavailable", "reason": "public_reference_unavailable", "contexts": None}
    checksum = index_hash(binding[1], budget.expires)
    with budget.scope(snapshot=True):
        dataset = catalog_dataset(db)
    games, coverage, contexts, seen, failed, incomplete, checked = sample(db, subject, budget)
    sample_identity = digest(canonical([subject, games, coverage, checked, sorted(seen), failed]))
    identity = {"sample_identity": sample_identity, "reference_index_sha256": checksum}
    sample_inputs = (
        games,
        seen,
        incomplete,
        not failed and not coverage["candidate_recheck_failed"],
    )
    result = {
        color: collect(
            db,
            root,
            subject,
            dataset,
            color,
            contexts[color],
            sample_inputs,
            budget,
            binding[1],
            identity,
            annotation,
        )
        for color in ("white", "black")
    }
    check(db, root, subject, binding, budget)
    return {
        "version": "opening-context-inventory-v1",
        "status": "prepared",
        "catalog": {"version": VERSION, "source": SOURCE, "sha256": GRAPH_SHA256},
        "reference_index_sha256": checksum,
        "sample": len(games),
        "sample_identity": sample_identity,
        "sample_failed": failed,
        "sample_incomplete": incomplete,
        "coverage": coverage,
        "limits": {
            "seconds": SECONDS,
            "games": 100,
            "owned_anchor_games": ANCHOR_GAMES,
            "owned_anchor_history_steps_per_parent": HISTORY_LIMIT,
            "parents_per_color": 2,
            "choices_per_parent": 2,
        },
        "contexts": result,
    }
