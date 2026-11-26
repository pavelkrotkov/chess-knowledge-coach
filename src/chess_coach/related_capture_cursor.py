"""Bind pagination to the current transfer selection scope."""

import base64
import json

from .curriculum_capture_file_guard import current
from .fact_fingerprint import canonical, digest

PAGE = 4


def _cursor(offset, scope):
    return base64.urlsafe_b64encode(canonical([offset, scope]).encode()).decode()


def _offset(cursor, scope):
    if cursor is None:
        return 0
    try:
        if len(cursor) > 256:
            raise ValueError
        offset, saved = json.loads(base64.urlsafe_b64decode(cursor).decode())
        if type(offset) is not int or offset < 0 or offset % PAGE or saved != scope:
            raise ValueError
        return offset
    except (ValueError, TypeError, UnicodeError):
        raise ValueError("transfer cursor changed; restart") from None


def bind_scope(db, subject, selected, files, prepared=None):
    if files != current(db, subject, db.capture_root):
        raise ValueError("capture source changed")
    if selected is None:
        return None
    source, rating, corpus, ordered, scope, diagnostics = selected
    inputs = ["capture-certificate-files-v1", scope, files]
    if prepared is not None:
        inputs.append(prepared)
    scope = digest(canonical(inputs))
    return source, rating, corpus, ordered, scope, diagnostics
