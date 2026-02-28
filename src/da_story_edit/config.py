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
    target = env_path or Path(".env")
    added = bootstrap_env_file(target)
    load_dotenv(target)
    parsed = dotenv_values(target)

    resolved: dict[str, str] = {}
    missing: list[str] = []
    for var in CONFIG_REGISTRY:
        env_value = os.getenv(var.name)
        file_value = parsed.get(var.name)
        env_value_stripped = (env_value or "").strip()
        value = (env_value_stripped or file_value or "").strip()
        if var.required and not value:
            missing.append(var.name)
        resolved[var.name] = value

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
