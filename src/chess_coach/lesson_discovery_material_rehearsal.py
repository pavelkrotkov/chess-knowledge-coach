"""Preflight source-bound discovered-material rehearsals for a live lesson."""

import sqlite3

from .discovery_material_contract import MAPPER, PRACTICE
from .discovery_material_practice import resolve


def attach(db, learner, lesson):
    if lesson["family"] != MAPPER:
        return
    for example in lesson["examples"]:
        try:
            resolve(db, PRACTICE, str(example["evidence_id"]), learner)
        except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError, AttributeError):
            continue
        example["discovery_material_rehearsal"] = True
