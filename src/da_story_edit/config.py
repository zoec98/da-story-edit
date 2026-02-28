from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values, load_dotenv


@dataclass(frozen=True)
class ConfigVar:
    name: str
    description: str
    required: bool = True
    example: str | None = None


CONFIG_REGISTRY: tuple[ConfigVar, ...] = (
    ConfigVar(
        name="DA_CLIENT_ID",
        description="OAuth2 client ID from the DeviantArt developer app settings.",
        example="12345",
    ),
    ConfigVar(
        name="DA_CLIENT_SECRET",
        description="OAuth2 client secret from the DeviantArt developer app settings.",
        example="replace-me",
    ),
    ConfigVar(
        name="DA_REDIRECT_URI",
        description="OAuth2 redirect URI configured on your DeviantArt app.",
        example="http://localhost:8765/callback",
    ),
    ConfigVar(
        name="DA_REFRESH_TOKEN",
        description="OAuth2 refresh token used to mint fresh access tokens.",
        required=False,
        example="replace-me",
    ),
    ConfigVar(
        name="DA_ACCESS_TOKEN",
        description="Current OAuth2 access token (optional cache).",
        required=False,
        example="replace-me",
    ),
)


class ConfigError(RuntimeError):
    """Raised when required environment configuration is missing."""


def _render_template_entry(var: ConfigVar) -> str:
    lines = [f"# {var.description}"]
    if var.example:
        lines.append(f"# Example: {var.example}")
    lines.append(f"{var.name}=")
    return "\n".join(lines)


def bootstrap_env_file(env_path: Path) -> list[str]:
    """Create or update .env with missing keys from the registry.

    Existing values are preserved. Missing keys are appended with instructions.
    Returns the list of keys that were added.
    """
    env_path.parent.mkdir(parents=True, exist_ok=True)

    if not env_path.exists():
        header = [
            "# da-story-edit environment configuration",
            "# Fill in required values before running live API operations.",
            "",
        ]
        env_path.write_text("\n".join(header), encoding="utf-8")

    existing = dotenv_values(env_path)
    added: list[str] = []
    blocks: list[str] = []

    for var in CONFIG_REGISTRY:
        if var.name in existing:
            continue
        added.append(var.name)
        blocks.append(_render_template_entry(var))

    if blocks:
        original = env_path.read_text(encoding="utf-8")
        suffix = "\n" if original and not original.endswith("\n") else ""
        appended = "\n\n".join(blocks) + "\n"
        env_path.write_text(f"{original}{suffix}{appended}", encoding="utf-8")

    return added


def load_and_validate_config(env_path: Path | None = None) -> dict[str, str]:
    """Load .env and validate required keys.

    Raises ConfigError with actionable instructions if values are missing.
    """
    required = [var.name for var in CONFIG_REGISTRY if var.required]
    return load_required_config(required, env_path)


def _resolve_values(env_path: Path) -> tuple[list[str], dict[str, str]]:
    added = bootstrap_env_file(env_path)
    load_dotenv(env_path)
    parsed = dotenv_values(env_path)

    resolved: dict[str, str] = {}
    for var in CONFIG_REGISTRY:
        env_value = os.getenv(var.name)
        file_value = parsed.get(var.name)
        env_value_stripped = (env_value or "").strip()
        value = (env_value_stripped or file_value or "").strip()
        resolved[var.name] = value
    return added, resolved


def load_config(env_path: Path | None = None) -> dict[str, str]:
    target = env_path or Path(".env")
    _, resolved = _resolve_values(target)
    return resolved


def load_required_config(
    required_names: list[str], env_path: Path | None = None
) -> dict[str, str]:
    target = env_path or Path(".env")
    added, resolved = _resolve_values(target)

    missing = [
        name for name in required_names if not (resolved.get(name) or "").strip()
    ]
    if missing:
        added_note = ""
        if added:
            added_note = f"\nAdded missing keys to {target}: {', '.join(added)}."
        raise ConfigError(
            "Configuration is incomplete.\n"
            f"Update {target} and set values for: {', '.join(missing)}."
            f"{added_note}\n"
            "Then run the command again."
        )
    return resolved


def upsert_env_values(env_path: Path, updates: dict[str, str]) -> None:
    """Update or append key/value pairs in .env while preserving unrelated lines."""
    env_path.parent.mkdir(parents=True, exist_ok=True)
    if not env_path.exists():
        bootstrap_env_file(env_path)

    lines = env_path.read_text(encoding="utf-8").splitlines()
    index_by_key: dict[str, int] = {}

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key:
            index_by_key[key] = idx

    for key, value in updates.items():
        new_line = f"{key}={value}"
        if key in index_by_key:
            lines[index_by_key[key]] = new_line
        else:
            if lines and lines[-1].strip():
                lines.append("")
            lines.append(new_line)

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
