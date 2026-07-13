import json
from pathlib import Path

from core.agent_runtime import handle_model_command
from core.model_router import (
    enable_auto_selection,
    get_model_status,
    get_selection_mode,
    set_current_profile,
)
from core.model_selection import ModelSelectionMode


def test_new_project_uses_auto_mode(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("core.model_router.is_ollama_available", lambda: False)
    assert get_selection_mode(tmp_path) is ModelSelectionMode.AUTO
    assert get_model_status(tmp_path)["current_profile"] == "code"
    assert get_model_status(tmp_path)["selection_mode"] == "auto"


def test_legacy_profile_file_migrates_to_manual(tmp_path: Path) -> None:
    path = tmp_path / "data" / "model_profile.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"current_profile": "docs"}), encoding="utf-8")
    assert get_selection_mode(tmp_path) is ModelSelectionMode.MANUAL


def test_set_profile_and_model_command_enable_manual(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    monkeypatch.setattr("core.model_router.is_ollama_available", lambda: False)
    handle_model_command("/model code", tmp_path)
    assert get_selection_mode(tmp_path) is ModelSelectionMode.MANUAL
    assert "Selection mode: manual" in capsys.readouterr().out


def test_auto_preserves_fallback_profile(tmp_path: Path) -> None:
    set_current_profile(tmp_path, "docs")
    enable_auto_selection(tmp_path)
    state = json.loads(
        (tmp_path / "data" / "model_profile.json").read_text(encoding="utf-8")
    )
    assert state == {"current_profile": "docs", "selection_mode": "auto"}

