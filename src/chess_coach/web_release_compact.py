"""Recognize only the exact compact source and dependency layout."""

import json
import re
import sys

from .web_release_compact_base import base_path
from .web_release_compact_paths import hashes_match, site_matches


def _marker(release, module):
    marker_path = release / "DEPENDENCY_RELEASE"
    if marker_path.is_symlink() or marker_path.stat().st_mode & 0o222:
        return None
    if module != release / "source/src/chess_coach/web_release.py":
        return None
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if not _valid_marker(marker):
        return None
    return marker


def _valid_marker(marker):
    return (
        set(marker) == {"version", "commit", "hashes", "python"}
        and marker["version"] == "compact-frozen-v1"
        and re.fullmatch(r"[0-9a-f]{40}", marker["commit"]) is not None
        and marker["python"] == list(sys.version_info[:3])
    )


def valid(environment, release, module):
    try:
        marker = _marker(release, module)
        if marker is None:
            return False
        base = base_path(release, marker["commit"])
        return bool(
            base
            and hashes_match(release, base, marker["hashes"])
            and site_matches(environment, release, base)
        )
    except (OSError, UnicodeError, ValueError, TypeError, KeyError):
        return False
