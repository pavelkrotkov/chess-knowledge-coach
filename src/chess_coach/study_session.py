"""Serialize publishing with the existing Lichess synchronization and cooldown."""

import fcntl
import os

import httpx

from .course_current import revalidate
from .db import Database
from .pipeline_cooldown import active_deadline
from .pipeline_cooldown_response import observe_response
from .pipeline_lock import pipeline_lock
from .pipeline_network_privacy import private_network_logs
from .study_publisher import publish
from .study_remote import Remote, StudyError


def publish_locked(path, planning, preview, course):
    intent = planning / "poc-study-336-intent.json"
    lock = os.open(planning / "poc-study-336.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pipeline_lock(path, sync=True):
            revalidate(path, preview, course)
            return _publish(path, intent, course)
    finally:
        os.close(lock)


def _publish(path, intent, course):
    db = Database(path)
    try:
        with private_network_logs(), httpx.Client(timeout=30.0, follow_redirects=False) as client:
            remote = Remote(
                os.environ["LICHESS_STUDY_TOKEN"],
                os.environ["CHESS_SUBJECT"],
                client,
                guard=lambda: _guard(db),
                observe=lambda response: observe_response(db, response, None),
            )
            return publish(remote, intent, course)
    finally:
        db.close()


def _guard(db):
    if active_deadline(db, None) is not None:
        raise StudyError("Lichess has requested a retry delay")
