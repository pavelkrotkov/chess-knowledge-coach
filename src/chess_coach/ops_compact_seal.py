"""Check every base release entry without following external links."""

import os
import stat
from pathlib import Path

from .ops_compact_links import link


def _entry(path, base):
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        link(path, base)
        return
    if info.st_uid != os.getuid() or info.st_mode & 0o222:
        raise ValueError("dependency release is not sealed")
    if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
        raise ValueError("dependency release has hard-linked files")
    if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
        raise ValueError("dependency release has an unsupported entry")


def _walk_error(_error):
    raise ValueError("dependency release cannot be inspected")


def sealed(base):
    _entry(base, base)
    for parent, directories, files in os.walk(base, followlinks=False, onerror=_walk_error):
        for name in [*directories, *files]:
            _entry(Path(parent) / name, base)
