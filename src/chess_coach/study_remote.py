"""Small fail-closed client for one private Lichess Study."""

import httpx

from .learner_identity import normalize_identity
from .study_authorization import StudyError, fail

BASE = "https://lichess.org"
SETTINGS = {
    "computer": "owner",
    "explorer": "owner",
    "cloneable": "nobody",
    "shareable": "owner",
    "chat": "nobody",
}


class Remote:
    def __init__(self, token, learner, client, guard=lambda: None, observe=lambda response: None):
        self.token = token
        self.learner = normalize_identity(learner)
        self.client = client
        self.guard = guard
        self.observe = observe

    def request(self, method, path, **kwargs):
        plain = kwargs.pop("headers_override", False)
        self.guard()
        try:
            response = self.client.request(
                method,
                BASE + path,
                headers={
                    "Authorization": "Bearer " + self.token,
                    "Accept": "application/json",
                    "Content-Type": "text/plain" if plain else "application/x-www-form-urlencoded",
                    "User-Agent": "Mozilla/5.0 (compatible; ChessCoach/1.0)",
                },
                **kwargs,
            )
        except httpx.RequestError:
            raise StudyError("network outcome is unknown") from None
        self.observe(response)
        if response.status_code != 200:
            fail(response.status_code)
        return response

    def account(self):
        value = self.request("GET", "/api/account").json()
        if not self.learner or normalize_identity(value.get("id")) != self.learner:
            raise StudyError("Study account does not match learner")
        return value

    def create(self, marker):
        result = self.request(
            "POST", "/api/study", data={"name": marker, "visibility": "private", **SETTINGS}
        ).json()
        return result.get("id")

    def upload(self, study_id, chapter):
        return self.request(
            "POST",
            f"/api/study/{study_id}/import-pgn",
            data={
                "pgn": chapter["pgn"],
                "name": chapter["name"],
                "orientation": chapter["orientation"],
                "mode": chapter.get("mode", "conceal"),
            },
        ).json()

    def export(self, study_id):
        return self.request(
            "GET",
            f"/api/study/{study_id}.pgn",
            params={"comments": "true", "variations": "true", "orientation": "true"},
        ).text
