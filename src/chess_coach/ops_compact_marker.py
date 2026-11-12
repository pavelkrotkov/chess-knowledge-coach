"""Require an intact standalone dependency-release marker."""


def marker(base, base_commit):
    marker = base / "COMMIT"
    if marker.is_symlink() or marker.read_text(encoding="ascii").strip() != base_commit:
        raise ValueError("dependency release marker differs")
    chain = base / "DEPENDENCY_RELEASE"
    if chain.exists() or chain.is_symlink():
        raise ValueError("dependency release must be standalone")
    if not _standalone(base):
        raise ValueError("dependency environment is not standalone")


def _standalone(base):
    config = (base / "venv" / "pyvenv.cfg").read_text(encoding="utf-8")
    entries = [
        line.split("=", 1)[1].strip().lower()
        for line in config.splitlines()
        if line.split("=", 1)[0].strip().lower() == "include-system-site-packages" and "=" in line
    ]
    return entries == ["false"]
