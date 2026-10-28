"""Keep HTTP client diagnostics from logging account URLs or credentials."""

import logging
import threading
from contextlib import contextmanager


class _SuppressThread(logging.Filter):
    def __init__(self):
        super().__init__()
        self.thread = threading.get_ident()

    def filter(self, record: logging.LogRecord) -> bool:
        return record.thread != self.thread


@contextmanager
def private_network_logs():
    names = (
        "httpx",
        "httpcore.connection",
        "httpcore.http11",
        "httpcore.http2",
        "httpcore.proxy",
        "httpcore.socks",
    )
    loggers = [logging.getLogger(name) for name in names]
    selected = _SuppressThread()
    for logger in loggers:
        logger.addFilter(selected)
    try:
        yield
    finally:
        for logger in loggers:
            logger.removeFilter(selected)
