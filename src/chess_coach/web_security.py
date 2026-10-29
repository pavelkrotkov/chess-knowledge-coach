"""Authenticate private proxy requests and protect state changes."""

import hmac
import secrets

from flask import abort, request, session


def install_security(app, login: str, origin: str, host: str) -> None:
    @app.before_request
    def authenticate():
        if request.headers.get("Tailscale-User-Login") != login or request.host != host:
            abort(403)
        if request.method == "POST":
            validate_post(origin)

    @app.context_processor
    def csrf_context():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        return {"csrf": session["csrf"]}

    @app.after_request
    def secure_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; style-src 'self'; script-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
        )
        return response


def validate_post(origin: str) -> None:
    submitted = request.form.get("csrf", "")
    token = session.get("csrf", "")
    if (
        request.headers.get("Origin") != origin
        or not token
        or not hmac.compare_digest(submitted, token)
    ):
        abort(403)
