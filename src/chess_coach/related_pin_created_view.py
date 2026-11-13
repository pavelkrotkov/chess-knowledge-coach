"""Show a completed supplied line's stored counterfactual pin witness."""

import json

import chess

from .related_pin_contract import ABSOLUTE_SLIDE_VERSION, CREATED_VERSION, SLIDE_VERSION
from .related_pin_created_view_certificate import certificate


def _describe(row, certificate):
    board = chess.Board(row["prompt_fen"])
    branch, proof = certificate["branch"], certificate["proof"]
    good = board.parse_uci(branch["move"])
    bad = board.parse_uci(branch["counterfactual"])
    if good == bad or good not in board.legal_moves or bad not in board.legal_moves:
        raise ValueError("pin contrast unavailable")
    result = {"good": board.san(good), "bad": board.san(bad)}
    board.push(bad)
    threat = board.parse_uci(proof["move"])
    if threat not in board.legal_moves:
        raise ValueError("pin threat unavailable")
    result.update(
        threat=board.san(threat), kind=proof["type"], pinned=proof["pinned"], rear=proof["rear"]
    )
    return result


def add_fields(result, row):
    if row["status"] != "line_completed":
        return
    try:
        binding = json.loads(row["provenance_json"]).get("related_pin") or {}
        if binding.get("rank_version") not in {
            CREATED_VERSION,
            SLIDE_VERSION,
            ABSOLUTE_SLIDE_VERSION,
        }:
            return
        proof = certificate(row, binding)
        from .related_pin_absolute_view import annotate

        result["pin_contrast"] = _describe(row, proof)
        annotate(result["pin_contrast"], row, proof, binding["rank_version"])
    except (ValueError, TypeError, KeyError, IndexError, StopIteration):
        return
