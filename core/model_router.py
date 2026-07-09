from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


DEFAULT_PROFILE = "code"
PROFILE_PATH = Path("data") / "model_profile.json"
MODEL_PROFILES = {
    "fast": {
        "model": "qwen2.5-coder:7b",
        "purpose": "fast responses",
    },
    "code": {
        "model": "qwen2.5-coder:14b",
        "purpose": "code and refactoring",
    },
    "docs": {
        "model": "qwen2.5-coder:14b",
        "purpose": "documents and RAG",
    },
    "deep": {
        "model": "qwen2.5-coder:32b",
        "purpose": "complex architecture and deep analysis",
    },
}


def get_model_profiles() -> dict:
    return MODEL_PROFILES.copy()


def _profile_path(project_root: Path) -> Path:
    return project_root / PROFILE_PATH


def get_current_profile(project_root: Path) -> dict:
    path = _profile_path(project_root)
    profile_name = DEFAULT_PROFILE

    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            candidate = data.get("current_profile", DEFAULT_PROFILE)
            if candidate in MODEL_PROFILES:
                profile_name = candidate
        except (OSError, json.JSONDecodeError):
            profile_name = DEFAULT_PROFILE

    profile = MODEL_PROFILES[profile_name].copy()
    profile["name"] = profile_name
    return profile


def set_current_profile(project_root: Path, profile_name: str) -> dict:
    profile_name = profile_name.strip().lower()
    if profile_name not in MODEL_PROFILES:
        raise ValueError(f"Unknown model profile: {profile_name}")

    path = _profile_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"current_profile": profile_name}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    profile = MODEL_PROFILES[profile_name].copy()
    profile["name"] = profile_name
    return profile


def resolve_model(profile_name: str | None = None) -> str:
    name = (profile_name or DEFAULT_PROFILE).strip().lower()
    if name not in MODEL_PROFILES:
        name = DEFAULT_PROFILE
    return MODEL_PROFILES[name]["model"]


def is_ollama_available() -> bool:
    return shutil.which("ollama") is not None


def get_installed_ollama_models() -> list[str]:
    if not is_ollama_available():
        return []

    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []

    if result.returncode != 0:
        return []

    models: list[str] = []
    for line in result.stdout.splitlines()[1:]:
        stripped = line.strip()
        if not stripped:
            continue
        name = stripped.split()[0]
        if name and name != "NAME":
            models.append(name)

    return models


def is_model_installed(model_name: str) -> bool:
    return model_name in get_installed_ollama_models()


def get_model_install_command(model_name: str) -> str:
    return f"ollama pull {model_name}"


def get_model_status(project_root: Path) -> dict:
    profile = get_current_profile(project_root)
    model = profile["model"]
    ollama_available = is_ollama_available()
    installed_models = get_installed_ollama_models() if ollama_available else []

    return {
        "current_profile": profile["name"],
        "current_model": model,
        "ollama_available": ollama_available,
        "model_installed": model in installed_models,
        "install_command": get_model_install_command(model),
    }
