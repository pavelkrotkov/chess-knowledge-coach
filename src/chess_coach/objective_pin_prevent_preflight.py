"""Check a source board and describe the separately bounded work."""

from . import material_exchange_rules, pin_defense_success, pin_proof, pin_scan
from .objective_pin_prevent_limits import (
    ANSWER_CAPTURE_PROBES,
    ANSWER_PROOFS,
    ROOT_MOVES,
    SOURCE_CAPTURE_PROBES,
    SOURCE_PROOFS,
)


def reserve(board):
    if len(list(board.legal_moves)) > ROOT_MOVES:
        raise ValueError("pin prevention work limit")
    limits = (
        pin_scan.MAX_MOVES,
        pin_scan.MAX_PINS,
        pin_proof.MAX_REPLIES,
        pin_defense_success.MAX_ROOT_MOVES,
        pin_defense_success.MAX_COUNTERFACTUAL_ROOTS,
    )
    if limits != (64, 16, 64, 64, 16):
        raise ValueError("pin prevention budget version changed")
    return {
        "source_pin_proofs": SOURCE_PROOFS,
        "answer_pin_proofs": ANSWER_PROOFS,
        "source_exposure_capture_probes": SOURCE_CAPTURE_PROBES,
        "answer_exposure_capture_probes": ANSWER_CAPTURE_PROBES,
        "proof_reply_limit": pin_proof.MAX_REPLIES,
        "nested_capture_attempts_per_proof": 2 * pin_proof.MAX_REPLIES,
        "answer_immediate_mate_moves": ROOT_MOVES,
        "exchange_nodes_per_search": material_exchange_rules.MAX_EXCHANGE_NODES,
        "scope": "per source refresh; publication refreshes the source again",
    }


def valid_key(version, key, expected):
    return (
        isinstance(key, str)
        and version == expected
        and key.isdecimal()
        and 0 < int(key) < 2**63
        and str(int(key)) == key
    )
