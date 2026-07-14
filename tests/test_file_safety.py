from pathlib import Path
from unittest.mock import patch

import pytest

from core.safety import FileSafetyError, safe_path, validate_writable_text_file


@pytest.mark.parametrize(
    "candidate",
    (
        "C:/Windows/system.ini",
        r"C:\Windows\system.ini",
        r"\\server\share\file.txt",
        "/etc/passwd",
        "../escape.txt",
        r"folder\..\escape.txt",
        "file.txt:stream",
        ".git/config",
        "data/workflows/state.json",
        "logs/runtime.log",
    ),
)
def test_portable_unsafe_paths_are_rejected(tmp_path: Path, candidate: str) -> None:
    with patch("core.safety.get_project_root", return_value=tmp_path):
        with pytest.raises(FileSafetyError):
            safe_path(candidate, must_exist=False)


def test_windows_separators_resolve_inside_project(tmp_path: Path) -> None:
    target = tmp_path / "src" / "module.py"
    target.parent.mkdir()
    target.write_text("value = 1\n", encoding="utf-8")
    with patch("core.safety.get_project_root", return_value=tmp_path):
        assert safe_path(r"src\module.py") == target.resolve()
        assert validate_writable_text_file(r"src\module.py") == target.resolve()


def test_symlink_component_is_rejected_for_write(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "file.txt").write_text("safe\n", encoding="utf-8")
    link = tmp_path / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    with patch("core.safety.get_project_root", return_value=tmp_path):
        with pytest.raises(FileSafetyError, match="Symbolic links"):
            validate_writable_text_file("linked/file.txt")
