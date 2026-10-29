"""Behavioral checks for bounded and resumable official snapshot acquisition."""

import hashlib
import json
import subprocess
import time
from pathlib import Path

import httpx
import pytest

from chess_coach.puzzle_snapshot import acquire
from chess_coach.puzzle_snapshot_http import strong_etag
from chess_coach.puzzle_snapshot_limits import Limits
from chess_coach.puzzle_snapshot_state import SOURCE_URL, statuses


class BrokenStream(httpx.SyncByteStream):
    def __init__(self, prefix):
        self.prefix = prefix

    def __iter__(self):
        yield self.prefix
        raise httpx.ReadTimeout("interrupted")


def archive():
    return subprocess.run(
        ["zstd", "-c", "-q"],
        input=b"PuzzleId,FEN\nexample,position\n",
        capture_output=True,
        check=True,
    ).stdout


def limits(**changes):
    values = dict(
        max_archive_bytes=100000,
        max_csv_bytes=100000,
        reserve_bytes=0,
        seconds=10,
        connect_timeout=1,
        read_timeout=1,
    )
    values.update(changes)
    return Limits(**values)


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def response(content, etag='"v1"'):
    return httpx.Response(
        200,
        headers={"content-length": str(len(content)), "etag": etag},
        stream=httpx.ByteStream(content),
    )


def test_complete_manifest_and_ready_version_is_immutable(tmp_path):
    data = archive()
    with client(lambda request: response(data)) as c:
        manifest = acquire(tmp_path, "v1", limits(), client=c)
        assert manifest["source_url"] == SOURCE_URL
        assert manifest["archive_sha256"] == hashlib.sha256(data).hexdigest()
        csv = Path(manifest["csv_path"]).read_bytes()
        assert manifest["csv_sha256"] == hashlib.sha256(csv).hexdigest()
        assert manifest["hash_origin"] == "locally computed"
        assert statuses(tmp_path)[0]["phase"] == "ready"
        with pytest.raises(FileExistsError):
            acquire(tmp_path, "v1", limits(), client=c)


def test_interrupted_download_resumes_exact_range(tmp_path):
    data = archive()
    cut = len(data) // 2
    requests = []

    def handler(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(
                200,
                headers={"content-length": str(len(data)), "etag": '"v1"'},
                stream=BrokenStream(data[:cut]),
            )
        assert request.headers["range"] == f"bytes={cut}-"
        assert request.headers["if-range"] == '"v1"'
        return httpx.Response(
            206,
            headers={
                "content-length": str(len(data) - cut),
                "content-range": f"bytes {cut}-{len(data) - 1}/{len(data)}",
                "etag": '"v1"',
            },
            stream=httpx.ByteStream(data[cut:]),
        )

    with client(handler) as c:
        with pytest.raises(httpx.ReadTimeout):
            acquire(tmp_path, "v1", limits(), client=c)
        result = acquire(tmp_path, "v1", limits(), client=c)
    assert result["archive_sha256"] == hashlib.sha256(data).hexdigest()


@pytest.mark.parametrize("bad", ["status", "range", "length", "etag"])
def test_changed_or_invalid_response_never_appends(tmp_path, bad):
    data = archive()
    cut = len(data) // 2
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                200,
                headers={"content-length": str(len(data)), "etag": '"v1"'},
                stream=BrokenStream(data[:cut]),
            )
        headers = {
            "content-length": str(len(data) - cut),
            "content-range": f"bytes {cut}-{len(data) - 1}/{len(data)}",
            "etag": '"v1"',
        }
        if bad == "range":
            headers["content-range"] = f"bytes 0-{len(data) - 1}/{len(data)}"
        if bad == "length":
            headers["content-length"] = "1"
        if bad == "etag":
            headers["etag"] = '"v2"'
        return httpx.Response(
            200 if bad == "status" else 206, headers=headers, stream=httpx.ByteStream(data[cut:])
        )

    with client(handler) as c:
        with pytest.raises(httpx.ReadTimeout):
            acquire(tmp_path, "v1", limits(), client=c)
        partial = next(tmp_path.glob("puzzle-snapshots/v1/attempt-*/archive.zst"))
        with pytest.raises(ValueError):
            acquire(tmp_path, "v1", limits(), client=c)
        assert partial.read_bytes() == data[:cut]


@pytest.mark.parametrize("etag", ["", 'W/"weak"', None])
def test_no_strong_validator_restarts_in_new_attempt(tmp_path, etag):
    data = archive()
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        assert "range" not in request.headers
        if calls == 1:
            headers = {"content-length": str(len(data))}
            if etag is not None:
                headers["etag"] = etag
            return httpx.Response(200, headers=headers, stream=BrokenStream(data[:5]))
        return response(data)

    with client(handler) as c:
        with pytest.raises(httpx.ReadTimeout):
            acquire(tmp_path, "v1", limits(), client=c)
        acquire(tmp_path, "v1", limits(), client=c)
    assert len(list(tmp_path.glob("puzzle-snapshots/v1/attempt-*"))) == 2


def test_truncated_archive_does_not_publish(tmp_path):
    data = archive()[:-2]
    with client(lambda request: response(data)) as c, pytest.raises(ValueError, match="zstd"):
        acquire(tmp_path, "v1", limits(), client=c)
    assert not list(tmp_path.glob("puzzle-snapshots/*/manifest.json"))


def test_limits_and_provider_backoff(tmp_path):
    data = archive()
    with client(lambda request: response(data)) as c:
        with pytest.raises(ValueError, match="byte limit"):
            acquire(tmp_path, "bytes", limits(max_archive_bytes=1), client=c)
        with pytest.raises(OSError, match="reserve"):
            acquire(tmp_path, "disk", limits(reserve_bytes=10**18), client=c)
        with pytest.raises(ValueError, match="byte limit"):
            acquire(tmp_path, "decoded", limits(max_csv_bytes=1), client=c)
    calls = []
    with client(
        lambda request: calls.append(request) or httpx.Response(429, headers={"retry-after": "120"})
    ) as c:
        with pytest.raises(ValueError, match="backoff"):
            acquire(tmp_path, "backoff", limits(), client=c)
        with pytest.raises(ValueError, match="backoff"):
            acquire(tmp_path, "backoff", limits(), client=c)
        with pytest.raises(ValueError, match="backoff"):
            acquire(tmp_path, "another-version", limits(), client=c)
    assert len(calls) == 1
    state = json.loads(
        next(tmp_path.glob("puzzle-snapshots/backoff/attempt-*/state.json")).read_text()
    )
    assert state["retry_at"] > time.time()


def test_etag_validation():
    assert strong_etag('"a"')
    assert not strong_etag('W/"a"')
    assert not strong_etag('"unterminated')


def test_partial_corruption_is_rejected_before_network(tmp_path):
    data = archive()
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            200,
            headers={"content-length": str(len(data)), "etag": '"v1"'},
            stream=BrokenStream(data[:5]),
        )

    with client(handler) as c:
        with pytest.raises(httpx.ReadTimeout):
            acquire(tmp_path, "v1", limits(), client=c)
        partial = next(tmp_path.glob("puzzle-snapshots/v1/attempt-*/archive.zst"))
        partial.write_bytes(b"other")
        with pytest.raises(ValueError, match="hash differs"):
            acquire(tmp_path, "v1", limits(), client=c)
    assert len(calls) == 1


def test_truncated_http_response_does_not_publish(tmp_path):
    data = archive()

    def handler(request):
        return httpx.Response(
            200,
            headers={"content-length": str(len(data) + 5), "etag": '"v1"'},
            stream=httpx.ByteStream(data),
        )

    with client(handler) as c, pytest.raises(ValueError, match="truncated"):
        acquire(tmp_path, "v1", limits(), client=c)
    assert not list(tmp_path.glob("puzzle-snapshots/*/manifest.json"))


def test_deadline_and_invalid_limits(tmp_path):
    from chess_coach.puzzle_snapshot_budget import check_budget

    with pytest.raises(TimeoutError):
        check_budget(tmp_path, limits(), time.monotonic() - 1, 0, 0)
    with pytest.raises(ValueError, match="finite"):
        acquire(tmp_path, "v1", limits(seconds=float("nan")))


def test_cli_status_is_read_only(tmp_path, monkeypatch, capsys):
    import sys

    from chess_coach.cli import main

    monkeypatch.setattr(
        sys, "argv", ["chess-coach", "acquisition-status", "--project-root", str(tmp_path)]
    )
    main()
    assert json.loads(capsys.readouterr().out) == []
    assert list(tmp_path.iterdir()) == []


def test_corrupt_archive_retry_uses_new_attempt(tmp_path):
    data = archive()
    calls = []

    def handler(request):
        calls.append(request)
        return response(data[:-2] if len(calls) == 1 else data)

    with client(handler) as c:
        with pytest.raises(ValueError, match="zstd"):
            acquire(tmp_path, "v1", limits(), client=c)
        manifest = acquire(tmp_path, "v1", limits(), client=c)
    assert len(calls) == 2
    assert manifest["archive_sha256"] == hashlib.sha256(data).hexdigest()
    assert len(list(tmp_path.glob("puzzle-snapshots/v1/attempt-*"))) == 2


@pytest.mark.parametrize("target", ["attempt", "archive", "lock", "state", "manifest"])
def test_rejects_existing_symlinks_without_touching_external_files(tmp_path, target):
    from chess_coach.puzzle_snapshot_paths import new_attempt, version_dir
    from chess_coach.puzzle_snapshot_state import write_state

    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_file = outside / "external"
    outside_file.write_bytes(b"untouched")
    version = version_dir(project, "v1")
    if target == "attempt":
        (version / "attempt-linked").symlink_to(outside, target_is_directory=True)
    elif target == "archive":
        attempt = new_attempt(version)
        write_state(
            attempt, {"phase": "failed", "resumable": True, "etag": '"v1"', "downloaded_bytes": 9}
        )
        (attempt / "archive.zst").symlink_to(outside_file)
    elif target == "state":
        attempt = new_attempt(version)
        (attempt / "state.json").symlink_to(outside_file)
    else:
        (version / (".lock" if target == "lock" else "manifest.json")).symlink_to(outside_file)
    calls = []
    with (
        client(lambda request: calls.append(request) or response(archive())) as c,
        pytest.raises(ValueError, match="symlink"),
    ):
        acquire(project, "v1", limits(), client=c)
    assert calls == []
    assert outside_file.read_bytes() == b"untouched"


def test_status_and_backoff_do_not_follow_linked_version(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    base = project / "puzzle-snapshots"
    base.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (base / "linked").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        statuses(project)
    with (
        client(lambda request: response(archive())) as c,
        pytest.raises(ValueError, match="symlink"),
    ):
        acquire(project, "other", limits(), client=c)
