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


@pytest.mark.parametrize(
    "message", ["fixture import failed", "missing practice template", "missing board script"]
)
def test_verification_failures_have_private_explanations(tmp_path, message):
    from chess_coach.ops_install import _verify

    release = tmp_path / "release"
    binary = release / "venv" / "bin"
    binary.mkdir(parents=True, mode=0o700)
    python = binary / "python"
    python.write_text(f"#!/bin/sh\nprintf '%s\\n' '{message}' >&2\nexit 9\n")
    python.chmod(0o700)
    with pytest.raises(RuntimeError, match="verification failed"):
        _verify(release, tmp_path, {"PATH": "/usr/bin:/bin"}, [])
    log = release / "prepare-error.log"
    assert message in log.read_text() and "status: 9" in log.read_text()
    assert stat.S_IMODE(log.stat().st_mode) == 0o600


def test_diagnostics_bound_output_and_hide_truncated_secret(tmp_path):
    import sys

    from chess_coach.ops_diagnostics import MAX_DIAGNOSTIC_BYTES, run_checked

    release = tmp_path / "release"
    release.mkdir(mode=0o700)
    secret = b"fixture-secret-crossing-boundary"
    code = (
        "import sys; sys.stdout.buffer.write(b'x' * 65525 + "
        "b'fixture-secret-crossing-boundary' + b'z' * 100000); sys.exit(3)"
    )
    with pytest.raises(RuntimeError, match="installation failed"):
        run_checked(
            [sys.executable, "-I", "-B", "-c", code],
            cwd=tmp_path,
            environment={},
            release=release,
            stage="installation",
            secrets=[secret],
        )
    contents = (release / "prepare-error.log").read_bytes()
    assert len(contents) < MAX_DIAGNOSTIC_BYTES + 200
    assert b"[output truncated]" in contents
    assert secret not in contents and b"fixture-sec" not in contents


@pytest.mark.parametrize("kind", ["file", "symlink"])
def test_existing_diagnostic_path_is_preserved(tmp_path, kind):
    import sys

    from chess_coach.ops_diagnostics import run_checked

    release = tmp_path / "release"
    release.mkdir(mode=0o700)
    log = release / "prepare-error.log"
    victim = tmp_path / "existing"
    victim.write_text("preserve")
    if kind == "file":
        log.write_text("preserve")
    else:
        log.symlink_to(victim)
    with pytest.raises(RuntimeError, match="could not create private diagnostics"):
        run_checked(
            [sys.executable, "-I", "-B", "-c", "raise SystemExit(1)"],
            cwd=tmp_path,
            environment={},
            release=release,
            stage="installation",
            secrets=[],
        )
    assert (log.read_text() if kind == "file" else victim.read_text()) == "preserve"
    if kind == "symlink":
        assert log.is_symlink()


def test_proxy_credentials_are_redacted_from_diagnostics(tmp_path, monkeypatch):
    import sys

    from chess_coach.ops_diagnostics import run_checked
    from chess_coach.ops_private_env import environment_and_secrets

    monkeypatch.setenv("HTTPS_PROXY", "http://fixture-proxy-user:fixture-proxy-pass@proxy.invalid")
    environment, secrets = environment_and_secrets()
    release = tmp_path / "release"
    release.mkdir(mode=0o700)
    code = "import sys; print('fixture-proxy-user fixture-proxy-pass'); sys.exit(2)"
    with pytest.raises(RuntimeError):
        run_checked(
            [sys.executable, "-I", "-B", "-c", code],
            cwd=tmp_path,
            environment=environment,
            release=release,
            stage="installation",
            secrets=secrets,
        )
    text = (release / "prepare-error.log").read_text()
    assert "fixture-proxy-user" not in text and "fixture-proxy-pass" not in text
    assert "[redacted]" in text


def test_redaction_expansion_remains_bounded(tmp_path):
    import sys

    from chess_coach.ops_diagnostics import MAX_DIAGNOSTIC_BYTES, run_checked

    release = tmp_path / "release"
    release.mkdir(mode=0o700)
    code = "import sys; print('x' * 30000); sys.exit(1)"
    with pytest.raises(RuntimeError):
        run_checked(
            [sys.executable, "-I", "-B", "-c", code],
            cwd=tmp_path,
            environment={},
            release=release,
            stage="installation",
            secrets=[b"x"],
        )
    output = (release / "prepare-error.log").read_bytes()
    assert len(output) <= MAX_DIAGNOSTIC_BYTES + 100
    assert b"[output truncated]" in output


@pytest.mark.parametrize(
    "result", [None, {"status": "complete"}, {"status": "waiting"}, {"status": "failed"}]
)
def test_retry_service_reports_failed_sync_and_closes_database(monkeypatch, result):
    from chess_coach import ops_retry

    closed = []

    class FakeDatabase:
        def __init__(self, path):
            pass

        def close(self):
            closed.append(True)

    monkeypatch.setenv("LICHESS_USERNAME", "fixture")
    monkeypatch.setattr(ops_retry, "database_path", lambda: Path("fixture.sqlite"))
    monkeypatch.setattr(ops_retry, "Database", FakeDatabase)
    monkeypatch.setattr(ops_retry, "sync_result", lambda *args, **kwargs: result)
    processed = []
    monkeypatch.setattr(
        ops_retry, "process_objectives", lambda db, learner: processed.append(learner)
    )
    if result is not None and result["status"] == "failed":
        with pytest.raises(SystemExit, match="cooldown retry synchronization failed"):
            ops_retry.main()
    else:
        ops_retry.main()
    assert closed == [True] and processed == ["fixture"]


def test_release_verifier_requires_installed_board_script(tmp_path):
    import subprocess
    import sys

    from chess_coach.ops_install import _verify

    release = tmp_path / "release"
    environment = release / "venv"
    subprocess.run(
        ["uv", "venv", "--offline", "--python", sys.executable, str(environment)],
        check=True,
        capture_output=True,
        text=True,
    )
    site = (
        environment
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )
    package = site / "chess_coach"
    (package / "templates").mkdir(parents=True)
    (package / "static").mkdir()
    (package / "__init__.py").write_text("")
    for name in (
        "practice.html",
        "board.html",
        "practice_move_form.html",
        "practice_navigation.html",
        "practice_reveal.html",
    ):
        (package / "templates" / name).write_text("synthetic")
    (package / "static" / "coach.css").write_text("synthetic")
    with pytest.raises(RuntimeError, match="verification failed"):
        _verify(release, tmp_path, {"PATH": "/usr/bin:/bin"}, [])
    assert "missing board script" in (release / "prepare-error.log").read_text()
    (package / "static" / "board.js").write_text("synthetic")
    _verify(release, tmp_path, {"PATH": "/usr/bin:/bin"}, [])


def test_board_script_is_declared_for_wheel():
    import fnmatch
    import tomllib

    project = Path(__file__).resolve().parents[1]
    config = tomllib.loads((project / "pyproject.toml").read_text())
    patterns = config["tool"]["setuptools"]["package-data"]["chess_coach"]
    assert any(fnmatch.fnmatch("static/board.js", pattern) for pattern in patterns)
    assert (project / "src/chess_coach/static/board.js").is_file()
