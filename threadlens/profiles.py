from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .paths import default_config_path, ensure_private_dir, ensure_private_storage_path

DEFAULT_CONFIG = default_config_path()
SOURCE_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


class ProfileConfigError(ValueError):
    pass


@dataclass
class SourceProfile:
    name: str
    paths: list[str]
    format: str = "jsonl"
    session_key: str = "sessionId"
    message_key: str = "uuid"
    role_key: str = "message.role"
    text_key: str = "message.content"
    timestamp_key: str = "timestamp"
    cwd_key: str = "cwd"
    title_key: str = "title"
    resume_template: str = ""

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SourceProfile":
        return cls(
            name=str(value.get("name") or ""),
            paths=[str(path) for path in value.get("paths") or []],
            format=str(value.get("format") or "jsonl"),
            session_key=str(value.get("session_key") or "sessionId"),
            message_key=str(value.get("message_key") or "uuid"),
            role_key=str(value.get("role_key") or "message.role"),
            text_key=str(value.get("text_key") or "message.content"),
            timestamp_key=str(value.get("timestamp_key") or "timestamp"),
            cwd_key=str(value.get("cwd_key") or "cwd"),
            title_key=str(value.get("title_key") or "title"),
            resume_template=str(value.get("resume_template") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_source_name(name: str, reserved: set[str] | None = None) -> None:
    if not SOURCE_NAME_RE.fullmatch(name):
        raise ValueError("Source name must start with a letter and contain only letters, numbers, _ or -")
    if reserved and name in reserved:
        raise ValueError(f"Source name is reserved: {name}")


def load_profiles(config_path: Path = DEFAULT_CONFIG, *, strict: bool = False) -> dict[str, SourceProfile]:
    if not config_path.exists():
        return {}
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        if strict:
            raise ProfileConfigError(f"{config_path}: {exc}") from exc
        return {}
    except json.JSONDecodeError as exc:
        if strict:
            raise ProfileConfigError(f"{config_path}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc
        return {}

    if not isinstance(payload, dict):
        if strict:
            raise ProfileConfigError(f"{config_path}: expected a JSON object with a sources array")
        return {}
    raw_sources = payload.get("sources", [])
    if not isinstance(raw_sources, list):
        if strict:
            raise ProfileConfigError(f"{config_path}: expected sources to be an array")
        return {}

    profiles: dict[str, SourceProfile] = {}
    for index, raw_source in enumerate(raw_sources, 1):
        if not isinstance(raw_source, dict):
            if strict:
                raise ProfileConfigError(f"{config_path}: source entry {index} must be an object")
            continue
        profile = SourceProfile.from_dict(raw_source)
        if profile.name and SOURCE_NAME_RE.fullmatch(profile.name):
            profiles[profile.name] = profile
        elif strict:
            raise ProfileConfigError(f"{config_path}: source entry {index} has an invalid or missing name")
    return profiles


def save_profiles(profiles: dict[str, SourceProfile], config_path: Path = DEFAULT_CONFIG) -> None:
    ensure_private_dir(config_path.parent)
    payload = {"sources": [profile.to_dict() for profile in sorted(profiles.values(), key=lambda item: item.name)]}
    config_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ensure_private_storage_path(config_path)
