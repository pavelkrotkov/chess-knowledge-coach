"""Build a frozen, non-editable release without changing the active service."""

import argparse
import re
import subprocess
from pathlib import Path

from .ops_archive import archive as _archive
from .ops_install import install_release
from .ops_paths import release_paths
from .ops_seal import seal_release
from .ops_units import render_units


def stage_release(root: Path, commit: str, *, dependency_release: str | None = None) -> Path:
    root = root.resolve(strict=True)
    commit = _commit(root, commit)
    base = None
    if dependency_release:
        from .ops_compact_prepare import prepare

        base = prepare(root, commit, _commit(root, dependency_release))
    runtime, release, source = release_paths(root, commit)
    _archive(root, commit, source)
    if base:
        from .ops_compact_install import install

        install(source, release, runtime, *base)
    else:
        install_release(source, release, runtime)
    (release / "COMMIT").write_text(commit + "\n", encoding="ascii")
    render_units(root, release, commit)
    if base:
        from .ops_compact_verify import verify_identity

        verify_identity(release, runtime, commit)
    seal_release(release)
    return release


def _commit(root: Path, commit: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("release requires an explicit full commit SHA")
    result = subprocess.run(
        ["git", "rev-parse", "--verify", f"{commit}^{{commit}}"],
        cwd=root,
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()
    if result != commit:
        raise ValueError("release commit did not resolve exactly")
    return commit


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare a frozen project-local release")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument(
        "--dependency-release", help="full SHA of a sealed standalone dependency release"
    )
    args = parser.parse_args()
    result = stage_release(
        args.project_root, args.commit, dependency_release=args.dependency_release
    )
    print(f"Prepared release: {result.name}")


if __name__ == "__main__":
    main()
