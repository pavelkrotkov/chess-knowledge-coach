"""Acquire one fixed anonymous recent-source prefix without replacement."""

import time
from pathlib import Path

import httpx

from .opening_queue_files import read
from .opening_recent_capacity import check as capacity
from .opening_recent_publish import available, publish
from .opening_recent_transfer import RETRY_NAME, receive
from .tactical_study_path import planning

SECONDS = 60


def _wait(directory):
    marker = read(directory / RETRY_NAME)
    if marker and marker.get("not_before", 0) > time.time():
        raise ValueError("public source retry delay remains active")


def acquire(root, subject, *, client=None):
    root = Path(root).resolve(strict=True)
    directory, _ = planning(root, subject)
    _wait(directory)
    available(directory)
    capacity(root, directory)
    deadline = time.monotonic() + SECONDS
    if client is not None:
        content, identity = receive(client, directory, deadline)
    else:
        with httpx.Client(timeout=20.0, follow_redirects=False, trust_env=False) as own:
            content, identity = receive(own, directory, deadline)
    capacity(root, directory)
    return publish(directory, content, identity)
