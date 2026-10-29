"""Reconstruct and recheck a fork observation against its exact source."""

from .fork_observation import observe
from .material_opportunity_source import load_source
from .material_replay import source_inputs
from .material_source import prepare
from .material_source_marker import source_marker


def verified_fen(db, evidence, fact, *, observer=observe, _history=None):
    try:
        prepared = prepare(db, evidence["position_id"], evidence["subject"], history=_history)
        source = load_source(db, fact["detector_run_id"])
        if {k: v for k, v in source.items() if k != "reactivation"} != source_inputs(prepared):
            return None
        fresh = observer(
            prepared["board"],
            prepared["context"]["played_move"],
            prepared["best"],
            prepared["played"],
        )
        if fresh != fact["payload"]:
            return None
        if (
            source_marker(db, evidence["position_id"], evidence["game_id"], evidence["subject"])
            != prepared["source_marker"]
        ):
            return None
    except (ValueError, TypeError, KeyError):
        return None
    return prepared["context"]["pre_move_fen"]
