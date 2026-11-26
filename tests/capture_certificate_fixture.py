"""Build a private capture project and run the real bounded certificate worker."""

import json
import subprocess
import sys

from chess_coach.capture_game_trend_scan import run
from chess_coach.opening_queue_location import scope
from chess_coach.pipeline_lock import pipeline_lock


def project(tmp_path, name):
    root = tmp_path / name
    data = root / ".runtime" / "data"
    data.mkdir(parents=True, mode=0o700)
    (root / ".runtime").chmod(0o700)
    (root / ".runtime" / "planning").mkdir(mode=0o700)
    return root, data / "plan.sqlite"


def certify(db, subject, root):
    db.capture_root = scope(db, root, db.capture_root)
    with pipeline_lock(db.path):
        run(db, subject, root)


def cli(path, *args, check=True, source_guard=None):
    # Real fresh CLI: fail if an admission proof runs while reopening the source.
    guard = """
import chess_coach.material_opportunity_current as material
import chess_coach.objective_capture_snapshot as capture
def forbidden(*args, **kwargs):
    raise AssertionError("capture admission proof ran during CLI request")
material.verified_witness = forbidden
capture.judge = forbidden
"""
    if source_guard is not None:
        guard += """
import json, sys
import chess_coach.related_capture_features as features
owned_prompt, owned_move = json.load(sys.stdin)
actual_gain = features.capture_gain
def guarded_gain(board, move, target, **kwargs):
    if board.fen() == owned_prompt and move.uci() == owned_move:
        raise AssertionError("owned source proof ran during CLI request")
    return actual_gain(board, move, target, **kwargs)
features.capture_gain = guarded_gain
"""
    guard += """
from chess_coach.cli import main
main()
"""
    return subprocess.run(
        [sys.executable, "-c", guard, "--db", str(path), *args],
        capture_output=True,
        text=True,
        input=json.dumps(source_guard) if source_guard is not None else None,
        check=check,
        timeout=30,
    )
