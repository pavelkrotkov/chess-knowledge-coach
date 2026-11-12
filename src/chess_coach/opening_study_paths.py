"""Resolve the private project and learner for an opening Study."""

import os
import re
from pathlib import Path

from .tactical_study_path import planning as private_planning
from .web_paths import inside


def paths(root, version):
    if not re.fullmatch(r"[0-9a-f]{64}", version):
        raise ValueError("opening preview version differs")
    root = Path(root).resolve(strict=True)
    learner = os.environ["CHESS_SUBJECT"]
    planning, _ = private_planning(root, learner)
    data = (root / ".runtime" / "data").resolve(strict=True)
    if not data.is_relative_to(root):
        raise ValueError("database outside project")
    database = inside(data, os.environ["CHESS_DB"], existing=True)
    return root, learner, planning, database
