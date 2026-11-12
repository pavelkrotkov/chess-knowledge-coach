"""Validate the standalone interpreter and its installed locked distributions."""

import json
import subprocess
import sys
from pathlib import Path

from .ops_compact_dependency_check import check
from .ops_compact_distributions import distributions
from .ops_compact_probe import script as probe_script
from .ops_compact_probe import site_path
from .ops_private_env import environment_and_secrets


def base_interpreter(base, runtime):
    python = base / "venv" / "bin" / "python"
    if python.resolve(strict=True) != Path(sys.executable).resolve(strict=True):
        raise ValueError("dependency interpreter differs")
    script = probe_script()
    environment, _ = environment_and_secrets()
    result = subprocess.run(
        [str(python), "-I", "-B", "-c", script],
        cwd=runtime,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    value = json.loads(result.stdout)
    expected = [list(sys.version_info[:3]), sys.implementation.cache_tag, sys.base_prefix]
    site = site_path(base / "venv")
    if value[:3] != expected or value[3] != str(base / "venv") or value[4] != str(site):
        raise ValueError("dependency interpreter configuration differs")
    if site.is_symlink() or site.resolve(strict=True) != site:
        raise ValueError("dependency site packages are outside the release")
    if value[6] is not True:
        raise ValueError("dependency files are unavailable or outside the release")
    distributions(base / "source" / "uv.lock", value[5])
    check(python, runtime)
    return site
