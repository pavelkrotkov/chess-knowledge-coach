"""Revalidate and prepare a version-scoped private tactical destination."""

import os
from functools import partial

from .course_paths import paths
from .study_publisher import publish
from .study_session import _publish, locked
from .tactical_export_input import load
from .tactical_study_current import revalidate
from .tactical_study_destination import prepare
from .tactical_study_intents import intent
from .tactical_study_path import planning as private_planning


def prepare_locked(root, export_path, expected_hash):
    private_planning(root, os.environ["CHESS_SUBJECT"])
    database, planning, _, _ = paths(root, export_path, export_path, output=False)
    with locked(database, planning):
        export = load(root, export_path)
        with revalidate(database, export, expected_hash) as check:
            destination = intent(planning, expected_hash)
            course = {"course": export["export"], "course_sha256": expected_hash}
            return _publish(database, destination, course, action=partial(prepare, check=check))


def publish_locked(root, export_path, expected_hash):
    private_planning(root, os.environ["CHESS_SUBJECT"])
    database, planning, _, _ = paths(root, export_path, export_path, output=False)
    with locked(database, planning):
        export = load(root, export_path)
        with revalidate(database, export, expected_hash) as check:
            destination = intent(planning, expected_hash)
            course = {"course": export["export"], "course_sha256": expected_hash}
            return _publish(
                database,
                destination,
                course,
                action=partial(publish, check=check, strict=True),
                check=check,
            )
