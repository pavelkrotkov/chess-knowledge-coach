"""Bind and select bounded public material-defense consequences."""

from .material_contract import VERSION as MATERIAL_VERSION
from .material_exchange_rules import MAX_EXCHANGE_NODES, MAX_EXCHANGE_PLIES
from .opening_public_capture_pv_game import MAX_SEARCHES
from .opening_public_proof_versions import current as current_preparation

VERSION = "public-opening-defense-consequences-v1"


def policy(
    identity, *, forks=False, prevent=False, protection=False, capture_pv=False, window="initial"
):
    if forks or prevent or protection or capture_pv or window != "initial":
        raise ValueError("invalid defense observation selection")
    return {
        **identity,
        "version": VERSION,
        "policy": {
            **identity["policy"],
            "defense_pv": {
                "objective": "material_protection",
                "operation": "prevent",
                "producer_version": MATERIAL_VERSION,
                "searches_per_branch": MAX_SEARCHES,
                "phase_seconds": 10,
                "search_policy": "all-legal-roots-v2",
                "minimum_loss": 3,
                "minimum_score_gap_cp": 150,
                "exchange_nodes": MAX_EXCHANGE_NODES,
                "exchange_plies": MAX_EXCHANGE_PLIES,
            },
        },
    }


def selected(directory, identity, window):
    if window != "initial":
        raise ValueError("defense observation window unavailable")
    value, legacy = current_preparation(directory, identity, chosen=policy(identity))
    if value is not None and value["version"] != VERSION:
        return None, value, None
    return value, legacy, None
