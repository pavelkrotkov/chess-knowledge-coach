"""Report authorization and provider failures without exposing credentials."""


class StudyError(ValueError):
    """Study publication cannot safely proceed."""


class StudyHTTPError(StudyError):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def require_scopes(remote):
    result = remote.request(
        "POST", "/api/token/test", content=remote.token, headers_override=True
    ).json()
    details = result.get(remote.token)
    scopes = set((details or {}).get("scopes", "").split(","))
    if not {"study:read", "study:write"}.issubset(scopes):
        raise StudyError("Study token is invalid or missing required scopes")


def fail(status):
    messages = {
        401: "Lichess authentication failed",
        403: "Lichess permission or scope denied",
        429: "Lichess rate limit requested",
    }
    raise StudyHTTPError(status, messages.get(status, "Lichess request did not complete"))
