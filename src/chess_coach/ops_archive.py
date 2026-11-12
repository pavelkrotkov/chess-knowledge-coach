"""Archive one exact Git revision into its private release source."""

import io
import subprocess
import tarfile
from pathlib import Path


def archive(root: Path, commit: str, source: Path) -> None:
    archive = subprocess.run(
        ["git", "archive", "--format=tar", commit], cwd=root, capture_output=True, check=True
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as package:
        package.extractall(source, filter="data")
