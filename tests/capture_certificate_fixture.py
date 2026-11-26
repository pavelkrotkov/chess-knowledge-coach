"""Build a private capture project and run the real bounded certificate worker."""

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
