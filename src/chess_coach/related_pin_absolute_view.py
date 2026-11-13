"""Render the stored checking capture and supported reply after completion."""

import chess

from .related_pin_contract import ABSOLUTE_SLIDE_VERSION, SLIDE_VERSION


def describe(row, certificate):
    board = chess.Board(row["prompt_fen"])
    branch = certificate["branch"]
    board.push(board.parse_uci(branch["move"]))
    capture = board.parse_uci(branch["refutation"]["capture"])
    if capture not in board.legal_moves or not board.is_capture(capture):
        raise ValueError("pin capture unavailable")
    capture_san = board.san(capture)
    board.push(capture)
    reply = board.parse_uci(branch["refutation"]["reply"])
    if reply not in board.legal_moves:
        raise ValueError("pin reply unavailable")
    return {"capture": capture_san, "reply": board.san(reply)}


def annotate(contrast, row, proof, version):
    if version == ABSOLUTE_SLIDE_VERSION:
        contrast["mechanism"] = "absolute_slide"
        contrast.update(describe(row, proof))
    elif version == SLIDE_VERSION:
        contrast["mechanism"] = "slide"
