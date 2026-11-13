"""Validate an exact sealed standalone release used only for dependencies."""

import re

from .ops_compact_configuration import configuration
from .ops_compact_marker import marker
from .ops_compact_seal import sealed
from .ops_paths import private_directory


def _base_path(root, commit, base_commit):
    if not re.fullmatch(r"[0-9a-f]{40}", base_commit) or commit == base_commit:
        raise ValueError("dependency release requires a different full commit SHA")
    runtime = private_directory(root / ".runtime")
    releases = private_directory(runtime / "releases")
    base = releases / base_commit
    private_directory(base)
    if base.is_symlink() or base.resolve(strict=True) != base:
        raise ValueError("dependency release is outside the release layout")
    return base


def validate(root, commit, base_commit):
    base = _base_path(root, commit, base_commit)
    sealed(base)
    marker(base, base_commit)
    return base, configuration(root, base, base_commit, commit)
