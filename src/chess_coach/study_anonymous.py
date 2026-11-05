"""Check public access without bearer credentials, cookies, redirects or body reads."""

import httpx


def request(url):
    with (
        httpx.Client(timeout=30.0, follow_redirects=False, trust_env=False) as client,
        client.stream(
            "GET",
            url,
            headers={
                "Accept": "application/x-chess-pgn",
                "User-Agent": "Mozilla/5.0 (compatible; ChessCoach/1.0)",
            },
        ) as response,
    ):
        return response


def verify(remote, study_id):
    from .study_privacy import _identifier
    from .study_remote import BASE, StudyError

    _identifier(study_id)
    remote.guard()
    try:
        response = request(BASE + f"/api/study/{study_id}.pgn")
    except httpx.RequestError:
        raise StudyError("anonymous privacy check unavailable") from None
    remote.observe(response)
    if response.status_code not in (401, 403):
        raise StudyError("anonymous privacy check failed")
