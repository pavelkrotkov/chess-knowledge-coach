"""Prepare a sealed dependency base before creating a candidate release."""

import re

from .ops_compact_base import validate
from .ops_compact_interpreter import base_interpreter


def prepare(root, commit, base_commit):
    if not re.fullmatch(r"/[A-Za-z0-9_./-]+", str(root)):
        raise ValueError("project path cannot be used for a compact release")
    base, hashes = validate(root, commit, base_commit)
    site = base_interpreter(base, root / ".runtime")
    return base, base_commit, hashes, site
