"""Exercise private publishing and recovery with synthetic positions only."""

import io
import json

import chess
import chess.pgn
import httpx
import pytest

from chess_coach.course_pgn import chapter
from chess_coach.course_preview import preview_hash
from chess_coach.study_pgn_verify import matches
from chess_coach.study_publisher import publish
from chess_coach.study_remote import SETTINGS, Remote, StudyError


class Provider:
    def __init__(self):
        self.name = None
        self.created = 0
        self.uploaded = []
        self.private = True
        self.timeout_create = True
        self.timeout_upload = True
        self.scopes = "study:read,study:write"

    def request(self, method, url, **kwargs):
        assert kwargs["headers"]["User-Agent"] == "Mozilla/5.0 (compatible; ChessCoach/1.0)"
        path = httpx.URL(url).path
        request = httpx.Request(method, url)
        if path == "/api/account":
            return httpx.Response(
                200, json={"id": "learner", "username": "learner"}, request=request
            )
        if path == "/api/token/test":
            return httpx.Response(
                200, json={"fixture-token": {"scopes": self.scopes}}, request=request
            )
        if path == "/api/study/by/learner":
            rows = [{"id": "abcd1234", "name": self.name}] if self.name else []
            return httpx.Response(200, text="\n".join(map(json.dumps, rows)), request=request)
        if path == "/api/study" and method == "POST":
            self.created += 1
            self.name = kwargs["data"]["name"]
            if self.timeout_create:
                self.timeout_create = False
                raise httpx.ReadTimeout("uncertain", request=request)
            return httpx.Response(200, json={"id": "abcd1234"}, request=request)
        if path.startswith("/study/abcd1234"):
            chapters = [{"id": "empty", "name": "Empty"}]
            chapters.extend(
                {"id": f"ch{i:06d}", "name": item["name"]} for i, item in enumerate(self.uploaded)
            )
            value = {
                "study": {
                    "id": "abcd1234",
                    "name": self.name,
                    "ownerId": "learner",
                    "visibility": "private" if self.private else "public",
                    "settings": SETTINGS,
                    "chapters": chapters,
                }
            }
            if path != "/study/abcd1234":
                value["study"]["chapter"] = {"id": path.rsplit("/", 1)[-1], "conceal": 0}
            return httpx.Response(200, json=value, request=request)
        if path == "/api/study/abcd1234.pgn":
            return httpx.Response(200, text=self.export(), request=request)
        if path == "/api/study/abcd1234/import-pgn":
            item = kwargs["data"]
            assert item["mode"] == "conceal"
            self.uploaded.append(item)
            if self.timeout_upload:
                self.timeout_upload = False
                raise httpx.ReadTimeout("uncertain", request=request)
            return httpx.Response(200, json={"chapters": [{"id": "new"}]}, request=request)
        raise AssertionError(path)

    def export(self):
        games = []
        for item in self.uploaded:
            game = chess.pgn.read_game(io.StringIO(item["pgn"]))
            assert game is not None
            if game.end().board().is_checkmate():
                winner = "0-1 Black" if game.end().board().turn else "1-0 White"
                game.end().comment = winner + " wins by checkmate."
            game.headers["ChapterName"] = item["name"]
            game.headers["Orientation"] = item["orientation"]
            games.append(str(game))
        return "\n\n\n".join(games)


def test_private_publication_reconciles_timeouts_and_rejects_public_destination(tmp_path):
    snapshot = {
        "prompt_fen": chess.STARTING_FEN,
        "learner_color": "white",
        "lines": ["e2e4 e7e5", "e2e4 c7c5"],
        "provenance": {},
    }
    chapters = [
        chapter(f"Lesson {i}", "A source and a useful question.", snapshot, {}) for i in range(5)
    ]
    board = chess.Board()
    for move in ("f3", "e5", "g4"):
        board.push_san(move)
    mate = {
        "prompt_fen": board.fen(),
        "learner_color": "black",
        "lines": ["d8h4"],
        "provenance": {},
    }
    chapters[2] = chapter("Mate", "Find checkmate.", mate, {})
    body = {"preview_sha256": "fixture", "chapters": chapters}
    course = {"course": body, "course_sha256": preview_hash(body)}
    provider = Provider()
    remote = Remote("fixture-token", "learner", provider)
    intent = tmp_path / "intent.json"

    provider.scopes = "study:read"
    with pytest.raises(StudyError, match="scopes"):
        publish(remote, intent, course)
    assert not provider.created and not provider.uploaded
    provider.scopes = "study:read,study:write"
    with pytest.raises(StudyError, match="unknown"):
        publish(remote, intent, course)
    assert provider.created == 1 and not provider.uploaded
    provider.private = False
    with pytest.raises(StudyError, match="privacy"):
        publish(remote, intent, course)
    assert not provider.uploaded
    provider.private = True
    with pytest.raises(StudyError, match="unknown"):
        publish(remote, intent, course)
    assert len(provider.uploaded) == 1
    link = publish(remote, intent, course)
    assert link.endswith("/abcd1234")
    assert provider.created == 1 and len(provider.uploaded) == 5
    expected = {**chapters[2], "name": provider.uploaded[2]["name"]}
    assert matches(expected, provider.export())
    assert not matches(
        expected, provider.export().replace("0-1 Black wins by checkmate.", "Unrelated annotation.")
    )
    assert not matches(
        expected,
        provider.export().replace("0-1 Black wins by checkmate.", "1-0 White wins by checkmate."),
    )
    with_teaching = chess.pgn.read_game(io.StringIO(expected["pgn"]))
    assert with_teaching is not None
    with_teaching.end().comment = "Keep this teaching comment."
    assert not matches({**expected, "pgn": str(with_teaching)}, provider.export())
    assert json.loads(intent.read_text())["complete"] is True
    assert json.loads(intent.read_text())["verified_at"]
    assert publish(remote, intent, course) == link
    assert provider.created == 1 and len(provider.uploaded) == 5
    provider.name = "Unrelated study"
    with pytest.raises(StudyError, match="marker"):
        publish(remote, intent, course)
    assert len(provider.uploaded) == 5

    wrong = Remote("fixture-token", "someone-else", Provider())
    with pytest.raises(StudyError, match="account"):
        publish(wrong, tmp_path / "other.json", course)
