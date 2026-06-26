"""Small persistent user settings store for desktop/runtime choices."""

from __future__ import annotations

import json
import os
import platform
from pathlib import Path
from typing import Any

APP_NAME = "JARVIS"
SETTINGS_FILE = "settings.json"


def settings_dir() -> Path:
    """Return a writable per-user settings directory."""
    if platform.system() == "Darwin":
        root = Path.home() / "Library" / "Application Support"
        return root / APP_NAME

    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        return Path(xdg_config_home) / APP_NAME.lower()

    return Path.home() / f".{APP_NAME.lower()}"


def settings_path() -> Path:
    return settings_dir() / SETTINGS_FILE


def load_settings() -> dict[str, Any]:
    path = settings_path()
    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    return data if isinstance(data, dict) else {}


def save_settings(updates: dict[str, Any]) -> dict[str, Any]:
    settings = load_settings()
    settings.update(updates)

    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return settings
