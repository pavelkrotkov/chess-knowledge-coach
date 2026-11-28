"""Capacity checks for the explicit offline archive-pair operation."""

import shutil
import time

from .recovery_capacity import MIN_WORKING, PROJECT_LIMIT, RESERVE, allocated
from .recovery_gzip_capacity import MANIFEST_ALLOWANCE

ARCHIVE_LIMIT = 900_000_000
ALLOCATION_SLACK = 1024 * 1024


def available(root, target, deadline):
    reserve = MIN_WORKING + RESERVE + MANIFEST_ALLOWANCE + ALLOCATION_SLACK
    usage = allocated(root, deadline)
    free = shutil.disk_usage(target.parent).free
    return min(PROJECT_LIMIT - usage, free) - reserve


def require_space(root, target, deadline, remaining=0, credit=0):
    if available(root, target, deadline) + credit < remaining:
        raise ValueError("offline recovery capacity unavailable")
    deadline.check()


def archive_limit(root, target, deadline):
    limit = min(ARCHIVE_LIMIT, available(root, target, deadline))
    if limit <= 0:
        raise ValueError("offline archive capacity unavailable")
    return limit


class Guard:
    def __init__(self, root, target, deadline):
        self.root = root
        self.target = target
        self.deadline = deadline
        self.next_check = 0.0

    def check(self, remaining=0, *, force=False):
        self.deadline.check()
        if force or time.monotonic() >= self.next_check:
            require_space(self.root, self.target, self.deadline, remaining)
            self.next_check = time.monotonic() + 1
