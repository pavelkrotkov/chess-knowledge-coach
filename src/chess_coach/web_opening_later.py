"""Keep later-opportunity work optional on an already qualified decision."""

from flask import current_app

from .opening_experiment import qualified
from .opening_fit_later import assess
from .web_db import database


def opportunity(decision, comparisons, requested):
    if not requested:
        return None
    choice = next((item for item in decision["catalog"]["items"] if item["uci"] == requested), None)
    if not choice or not qualified(decision, choice, comparisons.get(requested, {})):
        return {"status": "unavailable"}
    return {
        "choice": choice,
        **assess(
            database(),
            current_app.config["PROJECT_ROOT"],
            current_app.config["SUBJECT"],
            decision,
            choice,
        ),
    }
