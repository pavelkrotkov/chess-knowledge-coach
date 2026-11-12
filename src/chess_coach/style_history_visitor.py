"""Select the bounded parser when replay has a work quota or deadline."""

from .ingest_reader import SilentGameBuilder
from .style_schedule_budget import CURRENT, LimitedBuilder
from .style_schedule_clock import DEADLINE


def visitor():
    return (
        LimitedBuilder
        if CURRENT.get() is not None or DEADLINE.get() is not None
        else SilentGameBuilder
    )
