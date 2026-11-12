"""Project-local release and service template checks."""

import json
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


def _compact_memory_controls(monkeypatch):
    from unittest.mock import MagicMock

    from chess_coach import (
        ops_compact_configuration,
        ops_compact_install,
        ops_compact_marker,
        ops_compact_prepare,
        ops_compact_verify,
        web_release_compact,
    )

    root, runtime, release, source = (MagicMock() for _ in range(4))
    root.resolve.return_value = root
    base, site = MagicMock(), MagicMock()
    commit, base_commit = "a" * 40, "b" * 40
    expected = (base, base_commit, {"uv.lock": "hash"}, site)
    prepare, install = MagicMock(return_value=expected), MagicMock()
    standalone = MagicMock()
    with monkeypatch.context() as patch:
        patch.setattr(ops_release, "_commit", lambda _root, value: value)
        patch.setattr(ops_release, "release_paths", lambda *_args: (runtime, release, source))
        patch.setattr(ops_release, "_archive", MagicMock())
        patch.setattr(ops_release, "install_release", standalone)
        patch.setattr(ops_release, "render_units", MagicMock())
        patch.setattr(ops_release, "seal_release", MagicMock())
        patch.setattr(ops_compact_prepare, "prepare", prepare)
        patch.setattr(ops_compact_install, "install", install)
        patch.setattr(ops_compact_verify, "verify_identity", MagicMock())
        assert ops_release.stage_release(root, commit, dependency_release=base_commit) is release
        prepare.assert_called_once_with(root, commit, base_commit)
        install.assert_called_once_with(source, release, runtime, *expected)
        standalone.assert_not_called()

    file = MagicMock()
    file.is_symlink.return_value = False
    file.is_file.return_value = True
    file.read_bytes.return_value = b"same"
    base = MagicMock()
    base.__truediv__.return_value.__truediv__.return_value = file
    with monkeypatch.context() as patch:
        patch.setattr(ops_compact_configuration, "_git_file", lambda *_args: b"same")
        import hashlib

        hashes = ops_compact_configuration.configuration(root, base, base_commit, commit)
        digest = hashlib.sha256(b"same").hexdigest()
        assert hashes == {name: digest for name in ("uv.lock", "pyproject.toml", ".python-version")}
        patch.setattr(ops_compact_configuration, "_git_file", lambda *_args: b"changed")
        with pytest.raises(ValueError, match="configuration changed"):
            ops_compact_configuration.configuration(root, base, base_commit, commit)

    marker, chain = MagicMock(), MagicMock()
    marker.is_symlink.return_value = False
    marker.read_text.return_value = base_commit
    chain.exists.return_value = True
    base.__truediv__.side_effect = lambda name: chain if name == "DEPENDENCY_RELEASE" else marker
    with pytest.raises(ValueError, match="standalone"):
        ops_compact_marker.marker(base, base_commit)
    marker.read_text.side_effect = FileNotFoundError()
    with pytest.raises(ValueError, match="marker unavailable"):
        ops_compact_marker.marker(base, base_commit)
    config = MagicMock()
    config.read_text.return_value = "include-system-site-packages = true\n"
    base.__truediv__.side_effect = None
    base.__truediv__.return_value.__truediv__.return_value = config
    assert not ops_compact_marker._standalone(base)

    valid = {
        "version": "compact-frozen-v1",
        "commit": base_commit,
        "hashes": hashes,
        "python": list(__import__("sys").version_info[:3]),
    }
    assert web_release_compact._valid_marker(valid)
    assert not web_release_compact._valid_marker({**valid, "commit": "invalid"})
    with monkeypatch.context() as patch:
        patch.setattr(web_release_compact, "_marker", lambda *_args: valid)
        patch.setattr(web_release_compact, "base_path", lambda *_args: base)
        patch.setattr(web_release_compact, "hashes_match", lambda *_args: True)
        patch.setattr(web_release_compact, "site_matches", lambda *_args: True)
        assert web_release_compact.valid(release, root, source)
        patch.setattr(web_release_compact, "site_matches", lambda *_args: False)
        assert not web_release_compact.valid(release, root, source)
    assert "chess_coach.web_server" in ops_compact_verify._script(Path("/source"), Path("/base"))

    # No files are created: exercise the venv builder, path binding and verification wiring.
    source, source_root, release, environment = (MagicMock() for _ in range(4))
    source.is_relative_to.return_value = True
    source.__truediv__.return_value = source_root
    source_root.is_symlink.return_value = False
    source_root.is_dir.return_value = True
    source_root.__str__.return_value = "/candidate/source/src"
    site, candidate_site, base = MagicMock(), MagicMock(), MagicMock()
    site.is_relative_to.return_value = True
    site.__str__.return_value = "/base/venv/site-packages"
    candidate_site.is_symlink.return_value = False
    candidate_site.is_dir.return_value = True
    marker, console, pth = MagicMock(), MagicMock(), MagicMock()
    environment.__str__.return_value = "/candidate/venv"
    environment.__truediv__.return_value.__truediv__.return_value = console
    release.__truediv__.side_effect = lambda name: environment if name == "venv" else marker
    candidate_site.__truediv__.return_value = pth
    builder, verified = MagicMock(), MagicMock()
    factory = MagicMock(return_value=builder)
    with monkeypatch.context() as patch:
        patch.setattr(ops_compact_install.venv, "EnvBuilder", factory)
        patch.setattr(ops_compact_install, "site_path", lambda _venv: candidate_site)
        patch.setattr(ops_compact_install, "verify", verified)
        ops_compact_install.install(
            source, release, runtime, base, base_commit, valid["hashes"], site
        )
    factory.assert_called_once_with(with_pip=False, symlinks=True)
    builder.create.assert_called_once_with(environment)
    assert pth.write_text.call_args.args[0] == "/candidate/source/src\n/base/venv/site-packages\n"
    stored = json.loads(marker.write_text.call_args.args[0])
    assert stored["commit"] == base_commit and stored["hashes"] == valid["hashes"]
    marker.chmod.assert_called_once_with(0o400)
    assert ' -I -B -m chess_coach.cli "$@"' in console.write_text.call_args.args[0]
    verified.assert_called_once_with(release, runtime, site)

    from chess_coach.ops_compact_distributions import distributions

    lock = MagicMock()
    lock.read_text.return_value = '[[package]]\nname="fixture-dep"\nversion="1.0"\n'
    distributions(lock, [["fixture_dep", "1.0"]])
    with pytest.raises(ValueError, match="differs"):
        distributions(lock, [["fixture_dep", "2.0"]])
    lock.read_text.return_value = '[[package]]\nname="Fixture.Dep"\nversion="1.0"\n'
    distributions(lock, [["fixture_dep", "1.0"]])

    # The isolated probe must reject metadata whose recorded package file is missing.
    import contextlib
    import io
    import sys

    from chess_coach import ops_compact_dependency_check, ops_compact_interpreter
    from chess_coach.ops_compact_probe import script as probe_script

    item = MagicMock()
    item.metadata = {"Name": "fixture-dep"}
    item.version = "1.0"
    item.files = ["missing.py"]
    item.locate_file.return_value = str(Path(sys.prefix) / "missing.py")
    with monkeypatch.context() as patch:
        import importlib.metadata

        patch.setattr(importlib.metadata, "distributions", lambda **_kwargs: [item])
        patch.setattr(Path, "is_file", lambda _path: False)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exec(probe_script(), {})
        assert json.loads(output.getvalue())[-1] is False
        item.locate_file.return_value = "/outside-release/file.py"
        patch.setattr(Path, "is_file", lambda _path: True)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exec(probe_script(), {})
        assert json.loads(output.getvalue())[-1] is False

    fake_run = MagicMock()
    fake_run.return_value.returncode = 0
    with monkeypatch.context() as patch:
        patch.setattr(ops_compact_dependency_check, "private_directory", lambda path: path)
        patch.setattr(ops_compact_dependency_check.subprocess, "run", fake_run)
        ops_compact_dependency_check.check(Path("/project/base/python"), Path("/project/.runtime"))
        command = fake_run.call_args.args[0]
        assert all(flag in command for flag in ("--offline", "--no-cache", "--no-python-downloads"))
        assert fake_run.call_args.kwargs["env"]["TMPDIR"] == "/project/.runtime/tmp"
        fake_run.return_value.returncode = 1
        with pytest.raises(ValueError, match="incomplete"):
            ops_compact_dependency_check.check(
                Path("/project/base/python"), Path("/project/.runtime")
            )

    base, environment, binary, python, site = (MagicMock() for _ in range(5))
    base.__truediv__.return_value = environment
    environment.__truediv__.return_value = binary
    binary.__truediv__.return_value = python
    python.resolve.return_value = Path(sys.executable).resolve()
    site.is_symlink.return_value = False
    site.resolve.return_value = site
    metadata = [
        list(sys.version_info[:3]),
        sys.implementation.cache_tag,
        sys.base_prefix,
        str(environment),
        str(site),
        [["fixture-dep", "1.0"]],
        False,
    ]
    with monkeypatch.context() as patch:
        patch.setattr(ops_compact_interpreter, "site_path", lambda _path: site)
        patch.setattr(ops_compact_interpreter, "distributions", MagicMock())
        check = MagicMock()
        patch.setattr(ops_compact_interpreter, "check", check)
        runner = MagicMock()
        runner.return_value.stdout = json.dumps(metadata)
        patch.setattr(ops_compact_interpreter.subprocess, "run", runner)
        with pytest.raises(ValueError, match="files are unavailable"):
            ops_compact_interpreter.base_interpreter(base, runtime)
        check.assert_not_called()
        metadata[-1] = True
        runner.return_value.stdout = json.dumps(metadata)
        assert ops_compact_interpreter.base_interpreter(base, runtime) is site
        check.assert_called_once_with(python, runtime)


def test_stage_archives_exact_commit_and_renders_fixed_release_units(tmp_path, monkeypatch):
    _compact_memory_controls(monkeypatch)
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
