"""Measure a legally replayed public candidate without an owned-game anchor."""

import os
import time
from pathlib import Path

from .analysis import detect_compatibility
from .analysis_configuration import engine_config
from .opening_measure_engine import measure
from .opening_queue_binding import V2
from .purpose_config import FINAL_NODES, FINAL_SECONDS
from .style_history_lines import history_safe


def configuration(engine, board):
    binary = Path(engine).resolve(strict=True)
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise ValueError("public comparison engine unavailable")
    count = board.legal_moves.count()
    config = engine_config(
        binary, FINAL_NODES, FINAL_SECONDS, None, count, 1, 16, detect_compatibility()
    )
    config.update(
        purpose="opening-public-comparison",
        purpose_policy=V2,
        candidate_set="all-legal-roots",
        requested_nodes=180000,
        requested_seconds=1.35,
        source_semantics="public-recorded-root-v1",
    )
    return binary, config


def analyze(board, move, engine, deadline):
    if time.monotonic() >= deadline or move not in {item.uci() for item in board.legal_moves}:
        raise ValueError("public comparison source unavailable")
    if not history_safe(board):
        raise ValueError("public comparison history unavailable")
    binary, config = configuration(engine, board)
    # This is a public source position: no owned position identifier exists.
    result = measure(binary, config, board, {"id": None, "uci": move}, move, deadline)
    _, current = configuration(engine, board)
    if current != config or time.monotonic() >= deadline:
        raise ValueError("public comparison configuration changed")
    return config, result
