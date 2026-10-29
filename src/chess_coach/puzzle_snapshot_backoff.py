"""Honor provider retry delays without automatic retry loops."""

import time
from datetime import UTC
from email.utils import parsedate_to_datetime


def retry_at(value):
    if value.isdecimal():
        return time.time() + max(60, int(value))
    try:
        return max(time.time() + 60, parsedate_to_datetime(value).astimezone(UTC).timestamp())
    except (ValueError, TypeError, OverflowError):
        return time.time() + 60
