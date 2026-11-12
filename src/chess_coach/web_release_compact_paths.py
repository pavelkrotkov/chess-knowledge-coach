"""Check the compact release's sealed base and plain path binding."""

import hashlib
import sysconfig
from pathlib import Path


def hashes_match(release, base, hashes):
    if set(hashes) != {"uv.lock", "pyproject.toml"}:
        return False
    for name in hashes:
        for root in (release, base):
            path = root / "source" / name
            if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != hashes[name]:
                return False
    return True


def site_matches(environment, release, base):
    paths = {"base": str(environment), "platbase": str(environment)}
    site = Path(sysconfig.get_path("purelib", vars=paths))
    base_env = base / "venv"
    base_site = Path(
        sysconfig.get_path("purelib", vars={"base": str(base_env), "platbase": str(base_env)})
    )
    if site.is_symlink() or base_site.is_symlink() or base_site.resolve(strict=True) != base_site:
        return False
    pth = site / "chess-coach-paths.pth"
    return not pth.is_symlink() and pth.read_text() == f"{release / 'source/src'}\n{base_site}\n"
