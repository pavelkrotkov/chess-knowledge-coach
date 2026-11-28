"""Hold the sole Linux lease until the offline source is unlinked."""

import fcntl
import os
import signal
from contextlib import ExitStack

from .recovery_gzip_snapshot import check_identity


class Lease:
    def __init__(self, source, expected, deadline):
        self.source = source
        self.expected = expected
        self.deadline = deadline
        self.broken = False
        self.removed = False
        self.fd = -1
        self.exit = ExitStack()

    def _signal(self, _signum, _frame):
        self.broken = True

    def __enter__(self):
        previous = signal.signal(signal.SIGIO, self._signal)
        self.exit.callback(signal.signal, signal.SIGIO, previous)
        try:
            self.fd = os.open(self.source, os.O_RDWR | os.O_NOFOLLOW)
            self.exit.callback(os.close, self.fd)
            fcntl.fcntl(self.fd, fcntl.F_SETOWN, os.getpid())
            fcntl.fcntl(self.fd, fcntl.F_SETLEASE, fcntl.F_WRLCK)
            self.check()
            return self
        except BaseException:
            self.exit.close()
            raise

    def check(self):
        self.deadline.check()
        if self.broken or fcntl.fcntl(self.fd, fcntl.F_GETLEASE) != fcntl.F_WRLCK:
            raise ValueError("offline recovery lease broken or pending")
        check_identity(self.source, self.fd, self.expected)

    def unlink(self):
        directory = os.open(self.source.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            self.check()
            os.unlink(self.source)
            self.removed = True
            os.fsync(directory)
        finally:
            os.close(directory)

    def __exit__(self, _type, _value, _traceback):
        self.exit.close()
