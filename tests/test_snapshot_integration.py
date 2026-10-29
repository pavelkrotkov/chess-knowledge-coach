"""Exercise the official snapshot handoff through the private CLI."""

import json
import subprocess
import sys

import httpx

from chess_coach.cli import main


def test_acquire_stage_resume_and_query(tmp_path, monkeypatch, capsys):
    csv = (
        b"PuzzleId,FEN,Moves,Rating,RatingDeviation,Popularity,NbPlays,Themes,GameUrl,OpeningTags\n"
        b"p1,6k1/8/6K1/2Q5/8/8/8/8 b - - 0 1,g8h8 c5f8,1200,80,90,12,mate mateIn1,,\n"
        b"p2,6k1/8/6K1/2Q5/8/8/8/8 b - - 0 1,g8h8 c5f8,1300,80,90,12,mate mateIn1,,\n"
    )
    compressed = subprocess.run(
        ["zstd", "-c", "-q"], input=csv, capture_output=True, check=True
    ).stdout
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"content-length": str(len(compressed)), "etag": '"synthetic"'},
            stream=httpx.ByteStream(compressed),
        )
    )
    monkeypatch.setattr(
        "chess_coach.puzzle_snapshot_run.make_client",
        lambda limits: httpx.Client(transport=transport),
    )

    def cli(*args):
        monkeypatch.setattr(
            sys, "argv", ["chess-coach", "--db", str(tmp_path / "coach.sqlite"), *args]
        )
        main()
        return json.loads(capsys.readouterr().out)

    manifest = cli(
        "acquire-puzzles",
        "--project-root",
        str(tmp_path),
        "--version",
        "synthetic",
        "--max-archive-bytes",
        "100000",
        "--max-csv-bytes",
        "100000",
        "--reserve-bytes",
        "0",
        "--seconds",
        "10",
    )
    stage = [
        "stage-puzzles",
        manifest["csv_path"],
        "--project-root",
        str(tmp_path),
        "--version",
        manifest["version"],
        "--csv-sha256",
        manifest["csv_sha256"],
        "--archive-sha256",
        manifest["archive_sha256"],
        "--source-url",
        manifest["source_url"],
        "--batch-size",
        "1",
        "--min-free-bytes",
        "0",
    ]
    first = cli(*stage, "--max-rows", "1")
    assert first["state"] == "staging" and first["accepted"] == 1
    assert cli("query-puzzles", "--version", "synthetic") == []
    completed = cli(*stage, "--max-rows", "0")
    assert completed["state"] == "ready" and completed["accepted"] == 2
    assert completed["source"] == manifest["source_url"]
    assert completed["csv_sha256"] == manifest["csv_sha256"]
    assert completed["archive_sha256"] == manifest["archive_sha256"]
    assert cli("corpus-status")[0]["state"] == "ready"
    result = cli("query-puzzles", "--version", "synthetic", "--theme", "mateIn1")
    assert [row["puzzle_id"] for row in result] == ["p1", "p2"]
