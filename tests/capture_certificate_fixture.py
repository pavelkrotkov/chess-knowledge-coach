"""Build a private capture project and run the real bounded certificate worker."""

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


def cli(path, *args, check=True):
    # Real fresh CLI: fail if an admission proof runs while reopening the source.
    guard = """
import chess_coach.material_opportunity_current as material
import chess_coach.objective_capture_snapshot as capture
def forbidden(*args, **kwargs):
    raise AssertionError("capture admission proof ran during CLI request")
material.verified_witness = forbidden
capture.judge = forbidden
from chess_coach.cli import main
main()
"""
    return subprocess.run(
        [sys.executable, "-c", guard, "--db", str(path), *args],
        capture_output=True,
        text=True,
        check=check,
        timeout=30,
    )
