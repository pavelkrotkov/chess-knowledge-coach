"""Read bounded host and cgroup memory availability."""

from pathlib import Path

from .native_upgrade_cgroup import available as cgroup_available


def _host_available():
    for line in Path("/proc/meminfo").read_text().splitlines():
        fields = line.split()
        if fields and fields[0] == "MemAvailable:" and len(fields) == 3 and fields[2] == "kB":
            return int(fields[1]) * 1024
    raise ValueError("host memory availability unknown")


def available():
    host = _host_available()
    cgroup = cgroup_available()
    return min(host, cgroup if cgroup is not None else host)
