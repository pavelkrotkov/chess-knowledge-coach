"""Create a minimal release venv backed by an explicitly sealed base."""

import json
import sys
import venv

from .ops_compact_interpreter import site_path
from .ops_compact_verify import verify


def install(source, release, runtime, base, base_commit, hashes, site):
    if not site.is_relative_to(base / "venv") or not source.is_relative_to(release):
        raise ValueError("release dependency paths are outside the selected layout")
    source_root = source / "src"
    if source_root.is_symlink() or not source_root.is_dir():
        raise ValueError("release source is unavailable")
    environment = release / "venv"
    venv.EnvBuilder(with_pip=False, symlinks=True).create(environment)
    candidate_site = site_path(environment)
    if candidate_site.is_symlink() or not candidate_site.is_dir():
        raise ValueError("release site packages unavailable")
    (candidate_site / "chess-coach-paths.pth").write_text(
        f"{source_root}\n{site}\n", encoding="utf-8"
    )
    console = environment / "bin" / "chess-coach"
    console.write_text(
        f'#!/bin/sh\nexec "{environment}/bin/python" -I -B -m chess_coach.cli "$@"\n',
        encoding="utf-8",
    )
    console.chmod(0o700)
    marker = release / "DEPENDENCY_RELEASE"
    marker.write_text(
        json.dumps(
            {
                "version": "compact-frozen-v1",
                "commit": base_commit,
                "hashes": hashes,
                "python": list(sys.version_info[:3]),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    marker.chmod(0o400)
    verify(release, runtime, site)
