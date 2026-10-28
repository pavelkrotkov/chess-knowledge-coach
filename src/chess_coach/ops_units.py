"""Render reviewed service templates for one immutable release."""

import os
import re
from pathlib import Path

from .ops_paths import private_directory

NAMES = ("chess-coach-web.service", "chess-coach-worker.service", "chess-coach-worker.timer")


def render_units(root: Path, release: Path, commit: str) -> Path:
    root = root.resolve(strict=True)
    if not re.fullmatch(r"/[A-Za-z0-9_./-]+", str(root)):
        raise ValueError("project path cannot be rendered safely into systemd units")
    runtime = private_directory(root / ".runtime")
    releases = private_directory(runtime / "releases")
    if release != releases / commit or (release / "COMMIT").read_text().strip() != commit:
        raise ValueError("release marker does not match the selected commit")
    unit_root = private_directory(runtime / "units", create=True)
    output = unit_root / commit
    output.mkdir(mode=0o700)
    for name in NAMES:
        _render_one(root, release, output, name)
    return output


def _render_one(root: Path, release: Path, output: Path, name: str) -> None:
    template = release / "source" / "ops" / "systemd" / (name + ".in")
    value = template.read_text(encoding="utf-8")
    value = value.replace("@ROOT@", str(root)).replace("@RELEASE@", str(release))
    value = value.replace("@COMMIT@", release.name)
    path = output / name
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(value)
