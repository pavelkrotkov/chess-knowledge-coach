"""Keep recovery space reserved while temporary artifacts grow."""

import shutil
import time

from .recovery_capacity import PROJECT_LIMIT, RESERVE, allocated
from .recovery_gzip_capacity import MANIFEST_ALLOWANCE


class Guard:
    def __init__(self, root, target, report, deadline):
        self.root = root
        self.target = target
        self.report = report
        self.deadline = deadline
        self.next_check = 0.0

    def check(self, remaining, *, force=False):
        self.deadline.check()
        if not force and time.monotonic() < self.next_check:
            return
        reserve = remaining + self.report["working_bytes"] + RESERVE + MANIFEST_ALLOWANCE
        if allocated(self.root, self.deadline) + reserve > PROJECT_LIMIT:
            raise ValueError("project storage reserve unavailable")
        if shutil.disk_usage(self.target.parent).free < reserve:
            raise ValueError("recovery disk reserve unavailable")
        self.next_check = time.monotonic() + 30
