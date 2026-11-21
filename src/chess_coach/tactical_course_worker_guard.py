"""Publish diagnostics only while their source snapshot remains current."""

import os

from .opening_queue_files import read
from .opening_queue_write import staged, sync


def write_diagnostic(slot, value, expected, offer, previous, budget):
    with staged(slot, value) as temporary, budget.publication():
        if read(slot) != expected or read(offer) != previous:
            raise ValueError("course request or offer changed")
        os.replace(temporary, slot)
    sync(slot.parent)


def save_diagnostic(slot, current, selection, offer, previous, budget):
    if budget is None or read(offer) != previous:
        raise ValueError("course offer changed")
    budget.check()
    value = {
        **current,
        "state": "unavailable",
        "coverage": selection["coverage"],
        "unavailable": selection["unavailable"],
    }
    write_diagnostic(slot, value, current, offer, previous, budget)
