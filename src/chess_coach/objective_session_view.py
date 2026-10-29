"""Add current objective verification status to the private session view."""

from .objective_contract import VERSION
from .objective_status import latest
from .unified_session_state import view


def display(db, row):
    result = view(row)
    if row["source_version"] == VERSION:
        result["verification"] = latest(db, row)
    return result
