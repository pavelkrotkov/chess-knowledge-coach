"""Select distinct first encounters from a bounded practice-session window."""

from collections import deque

from .mastery_time import parse_utc
from .mate_assessment_rows import rows
from .related_capture_objective import is_source
from .related_capture_position import prompt_key

MAX_ASSESSMENTS = 8


def select(db, subject):
    selected, limited = rows(db, subject)
    seen, found, uncertain = set(), deque(maxlen=MAX_ASSESSMENTS), False
    for row in selected:
        try:
            when = parse_utc(row["started_at"])
            uncertain |= when is None or when.isoformat() != row["started_at"]
            key = prompt_key(row["prompt_fen"])
            duplicate = key in seen
            seen.add(key)
            if duplicate or not is_source(row):
                continue
            if len(found) >= MAX_ASSESSMENTS:
                limited = True
            found.append(row)
        except (ValueError, TypeError, KeyError, IndexError, AttributeError):
            uncertain = True
    return list(found), limited or uncertain
