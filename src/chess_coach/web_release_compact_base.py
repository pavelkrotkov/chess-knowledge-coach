"""Validate the sealed standalone base referenced by a compact release."""


def _marker(base, name):
    marker, chain = base / "COMMIT", base / "DEPENDENCY_RELEASE"
    if marker.is_symlink() or chain.exists() or chain.is_symlink():
        return False
    return marker.read_text(encoding="ascii").strip() == name and not base.stat().st_mode & 0o222


def base_path(release, name):
    base = release.parent / name
    if base.is_symlink() or base == release or base.resolve(strict=True) != base:
        return None
    return base if _marker(base, name) else None
