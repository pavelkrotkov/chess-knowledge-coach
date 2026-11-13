"""Relate verified first-answer intervals to independent game windows."""

from .mastery_time import parse_utc
from .mate_assessment_compare import SAMPLE


def _time(value):
    result = parse_utc(value)
    if result is None:
        raise ValueError("assessment time unavailable")
    return result


def answer_end(entries):
    if len(entries) != 2 * SAMPLE:
        return None
    try:
        starts = [_time(item.get("started_at")) for item in entries]
        answers = [_time(item.get("answered_at")) for item in entries]
    except ValueError:
        return None
    return max(answers).isoformat() if _ordered(starts, answers) else None


def _ordered(starts, answers):
    return (
        len(set(starts)) == len(starts)
        and len(set(answers)) == len(answers)
        and all(answer > start for start, answer in zip(starts, answers, strict=True))
        and max(answers[:SAMPLE]) < min(starts[-SAMPLE:])
    )
