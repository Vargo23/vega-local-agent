from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.install_windows_launcher import add_path_entry, install_launcher, render_wrapper


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "vega.cmd"


pytestmark = pytest.mark.skipif(
    os.name != "nt",
    reason="Windows launcher test",
)


def _cmd() -> str:
    return os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe")


def test_launcher_uses_explicit_runtime_without_python_on_path() -> None:
    environment = os.environ.copy()
    environment["VEGA_PYTHON"] = sys.executable
    environment["PATH"] = ""
    environment.pop("VIRTUAL_ENV", None)

    completed = subprocess.run(
        [_cmd(), "/d", "/c", str(LAUNCHER)],
        cwd=ROOT,
        input="/exit\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
        env=environment,
    )

    assert completed.returncode == 0
    assert "VEGA / OPERATOR CONSOLE" in completed.stdout
    assert "Bye." in completed.stdout


def test_launcher_fails_clearly_when_no_runtime_is_available() -> None:
    environment = os.environ.copy()
    environment["PATH"] = ""
    environment.pop("VEGA_PYTHON", None)
    environment.pop("VIRTUAL_ENV", None)

    completed = subprocess.run(
        [_cmd(), "/d", "/c", str(LAUNCHER)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
        check=False,
        env=environment,
    )

    assert completed.returncode == 1
    assert "VEGA could not find Python" in completed.stderr


def test_launcher_does_not_make_tmp_a_runtime_contract() -> None:
    content = LAUNCHER.read_text(encoding="utf-8-sig").lower()

    assert ".tmp" not in content
    assert "vega_python" in content
    assert "virtual_env" in content
    assert "py -3" in content
    assert "%*" in content
    assert "%~dp0scripts\\vega.py" in content


def _write_stub_project(project_root: Path, *, exit_code: int = 0) -> None:
    project_root.mkdir(parents=True)
    (project_root / "vega.cmd").write_text(
        "\r\n".join(
            (
                "@echo off",
                'echo cwd=%CD%',
                'echo args=%*',
                f"exit /b {exit_code}",
                "",
            )
        ),
        encoding="utf-8",
    )


@pytest.mark.parametrize("project_name", ["VEGA project", "VEGA проект"])
def test_global_wrapper_handles_spaces_unicode_arguments_and_exit_code(
    tmp_path: Path, project_name: str
) -> None:
    project_root = tmp_path / project_name
    _write_stub_project(project_root, exit_code=23)
    result = install_launcher(
        project_root=project_root,
        launcher_dir=tmp_path / "bin",
        update_path=False,
    )

    completed = subprocess.run(
        [_cmd(), "/d", "/c", str(result.launcher_path), "alpha", "two words"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert completed.returncode == 23
    assert f"cwd={project_root}" in completed.stdout
    assert 'args=alpha "two words"' in completed.stdout


def test_global_wrapper_reports_missing_project(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    _write_stub_project(project_root)
    result = install_launcher(
        project_root=project_root,
        launcher_dir=tmp_path / "bin",
        update_path=False,
    )
    (project_root / "vega.cmd").unlink()

    completed = subprocess.run(
        [_cmd(), "/d", "/c", str(result.launcher_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert completed.returncode == 1
    assert "VEGA project launcher was not found" in completed.stderr


def test_global_wrapper_is_a_minimal_delegator(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    _write_stub_project(project_root)
    result = install_launcher(
        project_root=project_root,
        launcher_dir=tmp_path / "bin",
        update_path=False,
    )
    content = result.launcher_path.read_text(encoding="utf-8").lower()

    assert "scripts\\vega.py" not in content
    assert "python" not in content
    assert ".tmp" not in render_wrapper(ROOT).lower()
    assert "v2.13.0" not in content
    assert "v3.0.0" not in content
    assert "git switch" not in content
    assert "call \"%vega_project%\\vega.cmd\" %*" in content


def test_installer_creates_updates_backs_up_and_is_idempotent(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    _write_stub_project(project_root)
    launcher_dir = tmp_path / "bin"

    created = install_launcher(
        project_root=project_root,
        launcher_dir=launcher_dir,
        update_path=False,
    )
    assert created.action == "created"
    assert created.backup_path is None

    created.launcher_path.write_text("obsolete launcher\n", encoding="utf-8")
    updated = install_launcher(
        project_root=project_root,
        launcher_dir=launcher_dir,
        update_path=False,
    )
    assert updated.action == "updated"
    assert updated.backup_path is not None
    assert updated.backup_path.read_text(encoding="utf-8") == "obsolete launcher\n"

    unchanged = install_launcher(
        project_root=project_root,
        launcher_dir=launcher_dir,
        update_path=False,
    )
    assert unchanged.action == "unchanged"
    assert unchanged.backup_path is None


def test_installer_does_not_duplicate_path(tmp_path: Path) -> None:
    entry = tmp_path / "VEGA bin"
    original = f"C:\\Windows;{entry};C:\\Tools"

    unchanged, changed = add_path_entry(original, entry)

    assert changed is False
    assert unchanged.split(";").count(str(entry)) == 1


def test_installer_appends_path_without_discarding_existing_entries(tmp_path: Path) -> None:
    entry = tmp_path / "VEGA bin"

    updated, changed = add_path_entry(r"C:\Windows;C:\Tools", entry)

    assert changed is True
    assert updated.startswith(r"C:\Windows;C:\Tools;")
    assert updated.endswith(str(entry.resolve()))
