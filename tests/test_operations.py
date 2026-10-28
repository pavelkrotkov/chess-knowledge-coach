"""Project-local release and service template checks."""

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from chess_coach import ops_release
from chess_coach.ops_paths import private_directory
from chess_coach.ops_seal import seal_release


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def fixture_repo(tmp_path: Path):
    root = tmp_path / "project"
    root.mkdir()
    (root / ".runtime").mkdir(mode=0o700)
    git(root, "init", "-q")
    git(root, "config", "user.name", "Fixture")
    git(root, "config", "user.email", "fixture@example.invalid")
    git(root, "config", "commit.gpgsign", "false")
    templates = root / "ops" / "systemd"
    templates.mkdir(parents=True)
    source = Path(__file__).resolve().parents[1] / "ops" / "systemd"
    for path in source.glob("*.in"):
        shutil.copyfile(path, templates / path.name)
    (root / "sample.txt").write_text("committed")
    git(root, "add", "ops", "sample.txt")
    git(root, "commit", "-q", "-m", "fixture")
    commit = git(root, "rev-parse", "HEAD")
    (root / "sample.txt").write_text("uncommitted")
    return root, commit


def test_stage_archives_exact_commit_and_renders_fixed_release_units(tmp_path, monkeypatch):
    root, commit = fixture_repo(tmp_path)

    def fake_install(source, release, runtime):
        assert (source / "sample.txt").read_text() == "committed"
        binary = release / "venv" / "bin"
        binary.mkdir(parents=True)
        python = binary / "python"
        python.write_text("#!/bin/sh\nexit 0\n")
        python.chmod(0o755)

    monkeypatch.setattr(ops_release, "install_release", fake_install)
    release = ops_release.stage_release(root, commit)
    assert (release / "COMMIT").read_text().strip() == commit
    assert not (release.stat().st_mode & 0o222)
    assert not ((release / "source" / "sample.txt").stat().st_mode & 0o222)
    units = root / ".runtime" / "units" / commit
    web = (units / "chess-coach-web.service").read_text()
    worker = (units / "chess-coach-worker.service").read_text()
    timer = (units / "chess-coach-worker.timer").read_text()
    assert f"ExecStart={release}/venv/bin/python -I -B" in web
    assert f"ExecStart={release}/venv/bin/python -I -B" in worker
    assert f"CHESS_RELEASE_SHA={commit}" in web
    assert "Restart=on-failure" in web and "Restart=no" in worker
    assert "OnUnitInactiveSec=15min" in timer
    assert "PYTHONPATH PYTHONHOME" in web and "PYTHONPATH PYTHONHOME" in worker
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in units.iterdir())
    assert not (root / ".runtime" / "current").exists()
    with pytest.raises(FileExistsError):
        ops_release.stage_release(root, commit)
    for directory, _dirs, files in os.walk(release):
        Path(directory).chmod(0o700)
        for name in files:
            path = Path(directory) / name
            if not path.is_symlink():
                path.chmod(0o600)


def test_release_rejects_short_sha_and_nonprivate_directories(tmp_path):
    root, commit = fixture_repo(tmp_path)
    with pytest.raises(ValueError, match="full commit"):
        ops_release.stage_release(root, commit[:8])
    (root / ".runtime").chmod(0o755)
    with pytest.raises(ValueError, match="private"):
        ops_release.stage_release(root, commit)


def test_seal_never_changes_symlink_target(tmp_path):
    release = tmp_path / "release"
    release.mkdir()
    outside = tmp_path / "external"
    outside.write_text("preserve")
    outside.chmod(0o600)
    (release / "link").symlink_to(outside)
    seal_release(release)
    assert stat.S_IMODE(outside.stat().st_mode) == 0o600
    assert (release / "link").is_symlink()
    release.chmod(0o700)


def test_private_directory_rejects_symlink(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir(mode=0o700)
    link = tmp_path / "link"
    link.symlink_to(actual, target_is_directory=True)
    with pytest.raises(ValueError, match="private"):
        private_directory(link)


def test_generated_units_pass_systemd_syntax_check(tmp_path, monkeypatch):
    if shutil.which("systemd-analyze") is None:
        pytest.skip("systemd-analyze unavailable")
    root, commit = fixture_repo(tmp_path)

    def fake_install(source, release, runtime):
        binary = release / "venv" / "bin"
        binary.mkdir(parents=True)
        executable = binary / "python"
        executable.write_text("#!/bin/sh\nexit 0\n")
        executable.chmod(0o755)

    monkeypatch.setattr(ops_release, "install_release", fake_install)
    release = ops_release.stage_release(root, commit)
    runtime = root / ".runtime"
    (runtime / "config.env").touch(mode=0o600)
    for name in ("logs", "data", "tmp", "cache"):
        (runtime / name).mkdir(mode=0o700)
    units = runtime / "units" / commit
    result = subprocess.run(
        ["systemd-analyze", "verify", "--man=no", *map(str, sorted(units.iterdir()))],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    for directory, _dirs, files in os.walk(release):
        Path(directory).chmod(0o700)
        for name in files:
            path = Path(directory) / name
            if not path.is_symlink():
                path.chmod(0o600)


def test_worker_uses_configured_project_database_and_existing_cli(tmp_path, monkeypatch):
    import sys

    from chess_coach import ops_worker

    root = tmp_path / "project"
    data = root / ".runtime" / "data"
    data.mkdir(parents=True)
    database = data / "restored.sqlite"
    database.write_bytes(b"fixture")
    release = root / ".runtime" / "releases" / ("a" * 40)
    (release / "venv").mkdir(parents=True)
    (release / "COMMIT").write_text(release.name)
    monkeypatch.setattr(sys, "prefix", str(release / "venv"))
    monkeypatch.setenv("CHESS_PROJECT_ROOT", str(root))
    monkeypatch.setenv("CHESS_DB", str(database))
    monkeypatch.setattr(sys, "argv", ["test"])
    captured = []
    monkeypatch.setattr(ops_worker, "cli_main", lambda: captured.append(sys.argv.copy()))
    ops_worker.main()
    assert captured == [["chess-coach", "--db", str(database), "process-pipeline"]]
    outside = tmp_path / "outside.sqlite"
    outside.write_bytes(b"fixture")
    monkeypatch.setenv("CHESS_DB", str(outside))
    with pytest.raises(ValueError, match="within"):
        ops_worker.main()


def test_seal_rejects_hardlinks_without_changing_other_files(tmp_path):
    release = tmp_path / "release"
    release.mkdir()
    outside = tmp_path / "other"
    outside.write_text("preserve")
    outside.chmod(0o600)
    os.link(outside, release / "shared")
    with pytest.raises(ValueError, match="hard-linked"):
        seal_release(release)
    assert stat.S_IMODE(outside.stat().st_mode) == 0o600
    assert outside.read_text() == "preserve"
