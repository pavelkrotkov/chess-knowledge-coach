"""Distinguish unsupported replay from expiration of the shared deadline."""

import json
import sqlite3
import time

from .opening_full_history_replay import replay


def attempt(db, row, decision, branch, deadline):
    try:
        return replay(db, row, decision, branch, deadline)
    except sqlite3.OperationalError:
        if time.monotonic() >= deadline:
            raise TimeoutError("public history deadline") from None
        return None
    except (ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError, sqlite3.Error):
        return None
