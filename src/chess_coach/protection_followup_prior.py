"""Revalidate a prior result and the selected follow-up at admission."""

import json

from .opening_queue_budget import BrowserBudget
from .protection_followup_context import context
from .protection_plan_history import report
from .tactical_course_budget import PreviewUnavailable
from .unified_sources import resolve_source


def prior(db, subject, corpus, evidence, attempt):
    if not isinstance(attempt, str) or not attempt or len(attempt) > 128 or not attempt.isascii():
        raise ValueError("protection follow-up unavailable")
    latest = report(db, subject, corpus, evidence)
    if (latest.get("status"), latest.get("evidence_id"), latest.get("attempt")) != (
        "correct",
        evidence,
        attempt,
    ):
        raise ValueError("protection follow-up unavailable")
    try:
        with BrowserBudget(db).scope(snapshot=False):
            row = db.connection.execute(
                "SELECT * FROM unified_sessions WHERE subject=? AND attempt_id=?",
                (subject, attempt),
            ).fetchone()
            if row is None:
                raise ValueError("protection follow-up unavailable")
            binding = json.loads(row["provenance_json"])["related_protection"]
            move = binding["assessment"]["proof"]["move"]
            return context(db, corpus, row["source_key"], binding, row["prompt_fen"], move)
    except PreviewUnavailable:
        raise ValueError("protection follow-up unavailable") from None


def selected(db, subject, corpus, evidence, attempt, assessment, chosen):
    if not assessment:
        raise ValueError("protection follow-up requires an assessment")
    expected = prior(db, subject, corpus, evidence, attempt)
    source_type, version, key, binding, lines = chosen
    if source_type != "corpus":
        raise ValueError("protection follow-up unavailable")
    prompt = resolve_source(db, source_type, version, key)["prompt_fen"]
    if context(db, version, key, binding, prompt, lines[0]) != expected:
        raise ValueError("protection follow-up changed")
