"""Assemble deterministic atomic structure features."""

from __future__ import annotations

from typing import Any, cast

import chess

from .structure_files import _half_open_files, _open_files
from .structure_geometry import _hanging, _isolated
from .structure_pawns import _backward
from .structure_position import _locked_center, _minority, _space


def extract_features(board: chess.Board) -> dict[str, Any]:
    """Return JSON-compatible deterministic atomic features for a position."""
    return {
        "open_files": _open_files(board),
        "half_open_files": {
            "white": _half_open_files(board, chess.WHITE),
            "black": _half_open_files(board, chess.BLACK),
        },
        "isolated_pawns": {
            "white": _isolated(board, chess.WHITE),
            "black": _isolated(board, chess.BLACK),
        },
        "backward_pawns": {
            "white": _backward(board, chess.WHITE),
            "black": _backward(board, chess.BLACK),
        },
        "hanging_pawns": {
            "white": _hanging(board, chess.WHITE),
            "black": _hanging(board, chess.BLACK),
        },
        "locked_center": _locked_center(board),
        "space": {"white": _space(board, chess.WHITE), "black": _space(board, chess.BLACK)},
        "minority_structure": {
            "white": _minority(board, chess.WHITE),
            "black": _minority(board, chess.BLACK),
        },
    }


def _structure_names(features: dict[str, object]) -> list[str]:
    names = []
    if features["open_files"]:
        names.append("open_files")
    if features["locked_center"]:
        names.append("locked_center")
    isolated = cast(dict[str, list[str]], features["isolated_pawns"])
    hanging = cast(dict[str, list[str]], features["hanging_pawns"])
    if any(isolated.values()):
        names.append("isolated_pawns")
    if any(hanging.values()):
        names.append("hanging_pawns")
    return names
