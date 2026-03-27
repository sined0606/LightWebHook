from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _read_secret_file(path: str | Path) -> str:
    secret_path = Path(path)
    if not secret_path.is_file():
        raise FileNotFoundError(f"Secret file not found: {secret_path}")

    secret = secret_path.read_text(encoding="utf-8").strip()
    if not secret:
        raise ValueError(f"Secret file is empty: {secret_path}")

    return secret


def _resolve_secret(
    *,
    direct_value: str | None = None,
    env_name: str | None = None,
    file_path: str | None = None,
    label: str,
) -> str:
    if direct_value:
        return direct_value

    if env_name:
        env_value = os.getenv(env_name, "").strip()
        if env_value:
            return env_value

    if file_path:
        return _read_secret_file(file_path)

    if env_name:
        raise ValueError(f"Environment variable for {label} is empty or missing: {env_name}")

    raise ValueError(f"No secret source configured for {label}")


@dataclass(frozen=True)
class WebhookConfig:
    name: str
    secret: str
    description: str | None = None


@dataclass(frozen=True)
class AppConfig:
    admin_username: str
    admin_secret: str
    webhooks: dict[str, WebhookConfig]


def _parse_webhook(name: str, raw: dict[str, Any]) -> WebhookConfig:
    if not isinstance(raw, dict):
        raise ValueError(f"Webhook '{name}' must be an object")

    secret = _resolve_secret(
        direct_value=raw.get("secret"),
        env_name=raw.get("secret_env"),
        file_path=raw.get("secret_file"),
        label=f"webhook '{name}'",
    )

    description = raw.get("description")
    if description is not None and not isinstance(description, str):
        raise ValueError(f"Webhook '{name}' description must be a string")

    return WebhookConfig(name=name, secret=secret, description=description)


def load_config() -> AppConfig:
    config_path = Path(os.getenv("APP_CONFIG_PATH", "config/webhooks.json"))
    if not config_path.is_file():
        raise FileNotFoundError(
            f"Config file not found: {config_path}. "
            "Copy config/webhooks.example.json to config/webhooks.json and adjust it."
        )

    with config_path.open("r", encoding="utf-8") as file_handle:
        raw_config = json.load(file_handle)

    if not isinstance(raw_config, dict):
        raise ValueError("Config root must be a JSON object")

    webhooks_section = raw_config.get("webhooks")
    if not isinstance(webhooks_section, dict) or not webhooks_section:
        raise ValueError("Config must contain at least one webhook in 'webhooks'")

    admin_username = os.getenv("ADMIN_USERNAME", "").strip() or raw_config.get("admin_username", "admin")
    if not isinstance(admin_username, str) or not admin_username.strip():
        raise ValueError("Config value 'admin_username' must be a non-empty string")

    admin_secret = _resolve_secret(
        direct_value=os.getenv("ADMIN_SECRET", "").strip() or raw_config.get("admin_secret"),
        env_name=raw_config.get("admin_secret_env"),
        file_path=os.getenv("ADMIN_SECRET_FILE", "").strip() or raw_config.get("admin_secret_file"),
        label="admin secret",
    )

    webhooks: dict[str, WebhookConfig] = {}
    for name, webhook_config in webhooks_section.items():
        webhooks[name] = _parse_webhook(name, webhook_config)

    return AppConfig(
        admin_username=admin_username.strip(),
        admin_secret=admin_secret,
        webhooks=webhooks,
    )
