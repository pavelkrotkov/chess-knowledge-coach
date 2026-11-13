"""Check active installed dependencies without network or shared caches."""

import subprocess

from .ops_paths import private_directory
from .ops_private_env import environment_and_secrets


def check(python, runtime):
    tmp = private_directory(runtime / "tmp")
    environment, _ = environment_and_secrets()
    environment.update(
        TMPDIR=str(tmp),
        UV_CACHE_DIR=str(runtime / "cache" / "uv"),
        UV_PYTHON_DOWNLOADS="never",
    )
    command = [
        "uv",
        "pip",
        "check",
        "--python",
        str(python),
        "--offline",
        "--no-cache",
        "--no-config",
        "--no-python-downloads",
    ]
    try:
        result = subprocess.run(
            command, cwd=runtime, env=environment, capture_output=True, timeout=30, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError("dependency compatibility check unavailable") from None
    if result.returncode:
        raise ValueError("installed dependencies are incomplete or incompatible")
