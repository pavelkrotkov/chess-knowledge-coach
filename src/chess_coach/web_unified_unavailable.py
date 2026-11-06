"""Keep stale owned mate errors separate from unavailable public sessions."""

from flask import abort, render_template

from .objective_contract import VERSION as MATE_ONE_VERSION
from .unified_session_state import session_row
from .unified_source_current import require_current


def unavailable(db, subject, attempt):
    try:
        row = session_row(db, attempt, subject)
        if (
            row["source_type"] == "own-game"
            and row["objective"] == "mate_in_one"
            and row["source_version"] == MATE_ONE_VERSION
        ):
            try:
                require_current(db, row)
            except (ValueError, TypeError, KeyError):
                return render_template(
                    "error.html", message="This practice source is unavailable or has changed."
                ), 410
    except ValueError:
        pass
    abort(404)
