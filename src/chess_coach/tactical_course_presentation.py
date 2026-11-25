"""A versioned, certificate-backed illustration for a fork chapter."""

VERSION = "owned-fork-illustration-v1"


def lines(chapter):
    presentation = chapter.get("presentation")
    if presentation is None:
        return chapter["source_snapshot"]["lines"]
    if presentation.get("version") != VERSION or not isinstance(presentation.get("lines"), list):
        raise ValueError("course presentation unavailable")
    return presentation["lines"]
