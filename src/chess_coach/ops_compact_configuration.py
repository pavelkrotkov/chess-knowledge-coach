"""Compare dependency configuration with both exact Git revisions."""

import hashlib
import subprocess


def _git_file(root, commit, name):
    result = subprocess.run(
        ["git", "show", f"{commit}:{name}"], cwd=root, capture_output=True, check=True
    )
    return result.stdout


def configuration(root, base, base_commit, commit):
    hashes = {}
    for name in ("uv.lock", "pyproject.toml", ".python-version"):
        path = base / "source" / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("dependency source configuration unavailable")
        data = path.read_bytes()
        if data != _git_file(root, base_commit, name) or data != _git_file(root, commit, name):
            raise ValueError("dependency configuration changed")
        hashes[name] = hashlib.sha256(data).hexdigest()
    return hashes
