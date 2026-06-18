from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Mapping


APP_NAME = "threadlens"


def default_data_dir(
    *,
    home: Path | None = None,
    environ: Mapping[str, str] | None = None,
    platform: str | None = None,
) -> Path:
    env = environ if environ is not None else os.environ
    home_path = home or Path.home()
    current_platform = platform or sys.platform

    if current_platform == "darwin":
        return home_path / "Library" / "Application Support" / APP_NAME
    if current_platform.startswith("win"):
        root = env.get("LOCALAPPDATA") or env.get("APPDATA")
        if root:
            return Path(root) / APP_NAME
        return home_path / "AppData" / "Local" / APP_NAME

    root = env.get("XDG_DATA_HOME")
    if root:
        return Path(root) / APP_NAME
    return home_path / ".local" / "share" / APP_NAME


def default_config_dir(
    *,
    home: Path | None = None,
    environ: Mapping[str, str] | None = None,
    platform: str | None = None,
) -> Path:
    env = environ if environ is not None else os.environ
    home_path = home or Path.home()
    current_platform = platform or sys.platform

    if current_platform == "darwin":
        return home_path / "Library" / "Application Support" / APP_NAME
    if current_platform.startswith("win"):
        root = env.get("APPDATA") or env.get("LOCALAPPDATA")
        if root:
            return Path(root) / APP_NAME
        return home_path / "AppData" / "Roaming" / APP_NAME

    root = env.get("XDG_CONFIG_HOME")
    if root:
        return Path(root) / APP_NAME
    return home_path / ".config" / APP_NAME


def default_db_path() -> Path:
    return default_data_dir() / "index.sqlite"


def default_config_path() -> Path:
    return default_config_dir() / "sources.json"


def ensure_private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        mode = path.stat().st_mode & 0o777
        if mode != 0o700:
            os.chmod(path, 0o700)


def ensure_private_file(path: Path) -> None:
    if path.exists() and os.name == "posix":
        mode = path.stat().st_mode & 0o777
        if mode != 0o600:
            os.chmod(path, 0o600)


def ensure_private_storage_path(path: Path) -> None:
    ensure_private_dir(path.parent)
    ensure_private_file(path)
