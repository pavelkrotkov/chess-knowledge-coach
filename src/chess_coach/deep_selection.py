"""Select bounded game decisions for later deep analysis, without inferring skills."""

from .db import Database
from .deep_selection_candidates import candidates
from .deep_selection_policy import select_positions
from .deep_selection_sampling import CONTROL_POLICY_VERSION
from .deep_selection_source import learner_key, source_snapshot
from .deep_selection_storage import persist_selection
from .deep_selection_validation import validate_request
from .motif_detectors import DETECTOR_VERSION as MOTIF_VERSION
from .tactical_opportunities import DETECTOR_VERSION as MATE_VERSION


def select_deep(db: Database, game_ids, *, learner, per_game=4, total=12, cp_gap=150, wdl_gap=0.1):
    validate_request(game_ids, per_game, total, cp_gap, wdl_gap)
    key = learner_key(learner)
    snapshots, unavailable = _snapshots(db, game_ids, learner)
    snapshots.sort(key=lambda item: (item["game_key"], item["game"]["id"]))
    result = []
    remaining = total
    seen_games = set()
    for source in snapshots:
        game_id = source["game"]["id"]
        if source["game_key"] in seen_games:
            result.append({"game_id": game_id, "status": "duplicate_game"})
            continue
        seen_games.add(source["game_key"])
        config = _config(per_game, total, min(per_game, remaining), cp_gap, wdl_gap)
        selected, coverage = select_positions(
            candidates(db, source, cp_gap, wdl_gap), source["game_key"], config["effective_limit"]
        )
        try:
            selection_id = persist_selection(db, source, learner, key, config, selected, coverage)
        except ValueError:
            result.append({"game_id": game_id, "status": "inputs_changed"})
            continue
        remaining -= len(selected)
        result.append(
            {
                "game_id": game_id,
                "status": "selected",
                "selection_id": selection_id,
                "coverage": coverage,
            }
        )
    return {"games": result + unavailable, "selected": total - remaining, "total_limit": total}


def _snapshots(db, game_ids, learner):
    snapshots, unavailable = [], []
    for game_id in sorted(game_ids):
        try:
            snapshots.append(source_snapshot(db, game_id, learner))
        except ValueError:
            unavailable.append(
                {
                    "game_id": game_id,
                    "status": "unavailable",
                    "reason": "A current compatible cheap analysis or learner attribution is unavailable.",
                }
            )
    return snapshots, unavailable


def _config(per_game, total, effective, cp_gap, wdl_gap):
    return {
        "per_game_limit": per_game,
        "invocation_limit": total,
        "effective_limit": effective,
        "cp_gap": cp_gap,
        "wdl_gap": float(wdl_gap),
        "motif_version": MOTIF_VERSION,
        "mate_version": MATE_VERSION,
        "control_policy": CONTROL_POLICY_VERSION,
    }
