"""Project-local release and service template checks."""

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from chess_coach import ops_release


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
    retry = (units / "chess-coach-retry.timer").read_text()
    assert "OnBootSec=5s" in retry and "OnUnitInactiveSec=10s" in retry
    assert "chess_coach.ops_retry" in (units / "chess-coach-retry.service").read_text()
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


def test_install_failure_saves_private_sanitized_diagnostics(tmp_path, monkeypatch):
    from chess_coach.ops_install import _install
    from chess_coach.ops_private_env import environment_and_secrets

    monkeypatch.setenv("CHESS_SUBJECT", "fixture-learner-secret")
    monkeypatch.setenv("LICHESS_USERNAME", "fixture-account-secret")
    monkeypatch.setenv("LICHESS_API_TOKEN", "fixture-token-secret")
    environment, secrets = environment_and_secrets()
    assert all(
        key not in environment for key in ("CHESS_SUBJECT", "LICHESS_USERNAME", "LICHESS_API_TOKEN")
    )
    binary = tmp_path / "bin"
    binary.mkdir()
    uv = binary / "uv"
    uv.write_text(
        "#!/bin/sh\nprintf '%s\\n' 'fixture build failed' 'fixture-learner-secret fixture-account-secret fixture-token-secret' >&2\nexit 7\n"
    )
    uv.chmod(0o700)
    environment["PATH"] = str(binary)
    release = tmp_path / "release"
    release.mkdir(mode=0o700)
    with pytest.raises(
        RuntimeError, match=r"installation failed; see .runtime/releases/release/prepare-error.log"
    ):
        _install(tmp_path, environment, release, secrets)
    log = release / "prepare-error.log"
    text = log.read_text()
    assert "fixture build failed" in text and "status: 7" in text
    assert "[redacted]" in text
    assert all(
        secret not in text
        for secret in ("fixture-learner-secret", "fixture-account-secret", "fixture-token-secret")
    )
    assert stat.S_IMODE(log.stat().st_mode) == 0o600
