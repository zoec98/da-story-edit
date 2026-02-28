from pathlib import Path

import pytest

from da_story_edit.config import (
    CONFIG_REGISTRY,
    ConfigError,
    bootstrap_env_file,
    load_and_validate_config,
    upsert_env_values,
)


def _all_required_values() -> dict[str, str]:
    return {
        var.name: f"value-for-{var.name.lower()}"
        for var in CONFIG_REGISTRY
        if var.required
    }


def _write_env(path: Path, values: dict[str, str]) -> None:
    lines = [f"{key}={value}" for key, value in values.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_bootstrap_creates_env_with_registry_keys(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    added = bootstrap_env_file(env_path)

    assert env_path.exists()
    assert added == [var.name for var in CONFIG_REGISTRY]
    content = env_path.read_text(encoding="utf-8")
    for var in CONFIG_REGISTRY:
        assert f"{var.name}=" in content


def test_bootstrap_preserves_existing_values_and_adds_missing(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    first = CONFIG_REGISTRY[0].name
    _write_env(env_path, {first: "already-set"})

    added = bootstrap_env_file(env_path)

    assert first not in added
    assert env_path.read_text(encoding="utf-8").count(f"{first}=") == 1
    for var in CONFIG_REGISTRY[1:]:
        assert var.name in added


def test_load_and_validate_raises_for_missing_required_values(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"

    with pytest.raises(ConfigError) as excinfo:
        load_and_validate_config(env_path)

    message = str(excinfo.value)
    assert "Configuration is incomplete." in message
    for var in CONFIG_REGISTRY:
        if not var.required:
            continue
        assert var.name in message


def test_load_and_validate_returns_values_when_complete(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    values = _all_required_values()
    _write_env(env_path, values)

    loaded = load_and_validate_config(env_path)

    for key, expected in values.items():
        assert loaded[key] == expected


def test_upsert_env_values_updates_existing_and_appends_new(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    _write_env(env_path, {"DA_CLIENT_ID": "old", "DA_REDIRECT_URI": "uri"})

    upsert_env_values(
        env_path,
        {
            "DA_CLIENT_ID": "new",
            "DA_REFRESH_TOKEN": "rtok",
        },
    )

    content = env_path.read_text(encoding="utf-8")
    assert "DA_CLIENT_ID=new" in content
    assert "DA_CLIENT_ID=old" not in content
    assert "DA_REDIRECT_URI=uri" in content
    assert "DA_REFRESH_TOKEN=rtok" in content
