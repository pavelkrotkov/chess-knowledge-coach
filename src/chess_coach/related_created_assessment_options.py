"""Show assessment controls only for independently certified visible examples."""

import time

from .related_capture_cursor import _offset
from .related_created_assessment import certificate

SECONDS = 2.0


def annotate(db, result, chosen, cursor):
    started = time.monotonic()
    offset = _offset(cursor, result["scope"])
    for visible, item in zip(result["items"], chosen[3][offset : offset + 4], strict=True):
        if time.monotonic() - started >= SECONDS:
            break
        if item["type"] != "corpus":
            continue
        try:
            certificate(
                db,
                item["version"],
                item["key"],
                item["matching_lines"],
                item["created_witness"],
                start=started,
                seconds=SECONDS,
            )
        except (ValueError, TypeError, KeyError, IndexError):
            continue
        visible["assessment_available"] = True
