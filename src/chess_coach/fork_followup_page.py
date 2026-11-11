"""Render explicit first and comparable fork finder requests."""

import sqlite3

import chess
from flask import current_app, render_template, request

from .fork_followup_finder import first, followup, latest
from .tactical_course_budget import PreviewUnavailable
from .web_board import board_rows
from .web_db import database


def page(*, matched):
    db = database()
    subject, corpus, secret = (
        current_app.config["SUBJECT"],
        current_app.config["CORPUS"],
        current_app.secret_key,
    )
    attempt = request.args.get("attempt") if matched else None
    evidence_id, result = None, None
    try:
        if matched:
            attempt = attempt or latest(db, subject, corpus)
            if attempt:
                evidence_id, result = followup(db, subject, corpus, secret, attempt)
        else:
            evidence_id, result = first(db, subject, corpus, secret)
        if result:
            item = result["items"][0]
            item["board"] = board_rows(item["fen"])
            item["color"] = "White" if chess.Board(item["fen"]).turn else "Black"
    except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError, PreviewUnavailable):
        result = None
    return render_template(
        "related_fork_assessment.html",
        result=result,
        evidence_id=evidence_id,
        matched=matched,
        prior=attempt,
    )
