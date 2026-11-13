"""Render explicit first and comparable fork finder requests."""

import sqlite3

import chess
from flask import current_app, render_template, request

from .fork_followup_finder import first, followup, latest
from .tactical_course_budget import PreviewUnavailable
from .web_board import board_rows
from .web_db import database


def _harder(db, subject, corpus, secret, attempt):
    from .fork_difficulty import by_attempt

    version = db.connection.execute("PRAGMA data_version").fetchone()[0]
    difficulty = by_attempt(db, subject, corpus, attempt)
    evidence, result = followup(db, subject, corpus, secret, attempt, difficulty=difficulty)
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != version:
        raise ValueError("fork selection changed")
    return evidence, result, difficulty


def _find(db, subject, corpus, secret, attempt, matched, harder):
    if not matched:
        evidence, result = first(db, subject, corpus, secret)
        return evidence, result, None
    if not attempt:
        return None, None, None
    if harder:
        return _harder(db, subject, corpus, secret, attempt)
    evidence, result = followup(db, subject, corpus, secret, attempt)
    return evidence, result, None


def page(*, matched):
    db = database()
    subject, corpus, secret = (
        current_app.config["SUBJECT"],
        current_app.config["CORPUS"],
        current_app.secret_key,
    )
    attempt = request.args.get("attempt") if matched else None
    evidence_id, result, difficulty = None, None, None
    harder = matched and request.args.get("harder") == "1"
    try:
        if matched:
            attempt = attempt or latest(db, subject, corpus)
        evidence_id, result, difficulty = _find(
            db, subject, corpus, secret, attempt, matched, harder
        )
        if result:
            item = result["items"][0]
            item["board"] = board_rows(item["fen"])
            item["color"] = "White" if chess.Board(item["fen"]).turn else "Black"
    except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError, PreviewUnavailable):
        result, difficulty = None, None
    return render_template(
        "related_fork_assessment.html",
        result=result,
        evidence_id=evidence_id,
        matched=matched,
        prior=attempt,
        harder=harder,
        difficulty=difficulty,
    )
