"""Validate private, project-local output paths for tactical previews."""

import os
from pathlib import Path

from .tactical_course_offer import PREPARE_SLOT, SLOT, STUDY_SLOT
from .web_paths import inside, socket_directory


def paths(root, output):
    if Path(output).name in {PREPARE_SLOT, SLOT, STUDY_SLOT}:
        raise ValueError("course output path is reserved")
    root = root.resolve(strict=True)
    planning = (root / ".runtime" / "planning").resolve(strict=True)
    data = (root / ".runtime" / "data").resolve(strict=True)
    if not planning.is_relative_to(root) or not data.is_relative_to(root):
        raise ValueError("course paths unavailable")
    socket_directory(root / ".runtime" / "entry")
    if planning.stat().st_uid != os.getuid() or planning.stat().st_mode & 0o022:
        raise ValueError("course planning directory unavailable")
    output = inside(planning, str(output), existing=False)
    if output.parent != planning:
        raise ValueError("course output must be directly in the private planning directory")
    return inside(data, os.environ["CHESS_DB"], existing=True), output
