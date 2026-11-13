"""Expose a checked material contrast only after the first legal answer."""

import json

import chess

from .related_created_contract import KEY


def add_fields(result, row):
    binding = json.loads(row["provenance_json"]).get(KEY)
    if not binding:
        return
    result["created_exposure"] = True
    # The target is visible, but the contrast remains hidden until a legal answer.
    _assessment(result, row, binding)
    if waiting(row, binding):
        result["created_waiting"] = True
        return
    evidence = binding.get("evidence_id")
    if result.get("created_assessment") and type(evidence) is int and 0 < evidence < 2**63:
        result["created_source_evidence"] = evidence
    try:
        result["created_contrast"] = _describe(row, binding)
    except (ValueError, TypeError, KeyError, IndexError):
        return


def _describe(row, binding):
    board = chess.Board(row["prompt_fen"])
    witness = binding["created_witness"]
    good, bad = (board.parse_uci(witness[key]) for key in ("good", "bad"))
    lines = json.loads(row["lines_json"])
    if not lines or lines[0][0] != good.uci():
        return
    good_san, bad_san = board.san(good), board.san(bad)
    board.push(bad)
    capture = board.parse_uci(witness["capture"])
    if not board.is_capture(capture):
        return
    return {
        "good": good_san,
        "bad": bad_san,
        "capture": board.san(capture),
    }


def waiting(row, binding=None):
    if binding is None:
        binding = json.loads(row["provenance_json"]).get(KEY)
    return bool(binding) and row["status"] == "active" and row["next_index"] == 0


def _assessment(result, row, binding):
    if binding.get("assessment"):
        board = chess.Board(row["prompt_fen"])
        target = binding["assessment"]["target"]
        piece = board.piece_at(chess.parse_square(target))
        if piece is None:
            raise ValueError("named piece unavailable")
        result.update(
            created_assessment=True,
            created_target=target,
            created_piece=chess.piece_name(piece.piece_type),
        )
