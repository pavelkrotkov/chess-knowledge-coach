"""Validate the standalone interpreter and its installed locked distributions."""

import json
import subprocess
import sys
import sysconfig
from pathlib import Path

from .ops_compact_distributions import distributions
from .ops_private_env import environment_and_secrets


def site_path(venv):
    return Path(sysconfig.get_path("purelib", vars={"base": str(venv), "platbase": str(venv)}))


def base_interpreter(base, runtime):
    python = base / "venv" / "bin" / "python"
    if python.resolve(strict=True) != Path(sys.executable).resolve(strict=True):
        raise ValueError("dependency interpreter differs")
    script = (
        "import json,sys,sysconfig; from importlib.metadata import distributions; "
        "site=sysconfig.get_paths()['purelib']; "
        "dists=[[d.metadata['Name'],d.version] for d in distributions(path=[site])]; "
        "print(json.dumps([list(sys.version_info[:3]),sys.implementation.cache_tag,"
        "sys.base_prefix,sys.prefix,site,dists]))"
    )
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
    distributions(base / "source" / "uv.lock", value[5])
    return site
