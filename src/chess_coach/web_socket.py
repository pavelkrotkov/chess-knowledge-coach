"""Hold an exclusive browser instance lock and safely recover stale sockets."""

import fcntl
import os
import stat
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def browser_socket(path: Path):
    lock = Path(str(path) + ".lock")
    flags = os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW
    descriptor = os.open(lock, flags, 0o600)
    try:
        _lock(descriptor)
        _remove_stale(path)
        yield
    finally:
        os.close(descriptor)


def _lock(descriptor: int) -> None:
    info = os.fstat(descriptor)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("browser lock file must be private and owned by the current user")
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise ValueError("another browser process holds the socket lock") from None


def _remove_stale(path: Path) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
        raise ValueError("existing browser socket path is not an owned socket")
    if _is_bound(path):
        raise ValueError("browser socket is already in use")
    current = path.lstat()
    if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
        raise ValueError("browser socket changed during startup")
    path.unlink()


def _is_bound(path: Path) -> bool:
    # Linux lists bound Unix sockets even when the process has not called listen().
    with open("/proc/net/unix", encoding="utf-8") as entries:
        for line in entries:
            fields = line.split(maxsplit=7)
            if len(fields) == 8 and fields[7].rstrip("\n") == str(path):
                return True
    return False
