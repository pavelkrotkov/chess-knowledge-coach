"""Read cgroup-v2 memory headroom conservatively."""

from pathlib import Path

CGROUP_ROOT = Path("/sys/fs/cgroup")


def available():
    lines = Path("/proc/self/cgroup").read_text().splitlines()
    groups = [line[3:] for line in lines if line.startswith("0::/")]
    if len(groups) != 1:
        raise ValueError("cgroup memory availability unknown")
    leaf = (CGROUP_ROOT / groups[0].lstrip("/")).resolve(strict=True)
    if not leaf.is_relative_to(CGROUP_ROOT) or not (leaf / "memory.current").is_file():
        raise ValueError("cgroup memory availability unknown")
    return _ancestors(leaf)


def _ancestors(leaf):
    available = []
    while leaf != CGROUP_ROOT:
        maximum, current = leaf / "memory.max", leaf / "memory.current"
        if not maximum.is_file() or not current.is_file():
            raise ValueError("cgroup memory availability unknown")
        limit = maximum.read_text().strip()
        used = int(current.read_text().strip())
        if limit != "max":
            available.append(max(0, int(limit) - used))
        leaf = leaf.parent
    return min(available) if available else None
