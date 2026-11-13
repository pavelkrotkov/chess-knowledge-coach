"""Return the exact current opening course as a private PGN."""

from flask import Response, abort, request


def download(course):
    if request.args.get("version") != course["version"]:
        abort(409, "The opening course changed. Open a new preview.")
    if not course["chapters"]:
        abort(404)
    document = "\n\n".join(item["pgn"] for item in course["chapters"]) + "\n"
    return Response(
        document,
        mimetype="application/x-chess-pgn",
        headers={
            "Content-Disposition": 'attachment; filename="unfamiliar-opening-course.pgn"',
            "Cache-Control": "private, no-store",
        },
    )
