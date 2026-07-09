from __future__ import annotations

import json
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
