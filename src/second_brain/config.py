from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
import os
from urllib.parse import urlparse


class ConfigError(ValueError):
    """Raised when runtime configuration is missing or unsafe."""


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _as_path(value: str, base_dir: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


@dataclass(frozen=True)
class AppConfig:
    app_env: str
    authorized_telegram_user_ids: tuple[str, ...]
    vault_path: Path
    database_url: str
    attachment_temp_dir: Path
    log_level: str
    hermes_internal_tool_token: str
    telegram_bot_token: str
    hermes_gateway_enabled: bool
    hermes_gateway_allowed_user_ids: tuple[str, ...]
    second_brain_core_url: str
    timezone: str
    vault_git_sync: bool
    project_root: Path

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def database_path(self) -> Path:
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            raise ConfigError("Only sqlite:/// DATABASE_URL is supported in Phase 0.")
        raw_path = self.database_url[len(prefix) :]
        return _as_path(raw_path, self.project_root)

    def validate(self) -> None:
        if self.app_env not in {"development", "test", "production"}:
            raise ConfigError("APP_ENV must be development, test, or production.")

        if not self.vault_path.exists():
            raise ConfigError(f"VAULT_PATH does not exist: {self.vault_path}")

        if not self.vault_path.is_dir():
            raise ConfigError(f"VAULT_PATH must be a directory: {self.vault_path}")

        if not self.database_url.startswith("sqlite:///"):
            raise ConfigError("DATABASE_URL must use sqlite:/// for Phase 0.")

        if self.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
            raise ConfigError("LOG_LEVEL must be DEBUG, INFO, WARNING, or ERROR.")

        parsed_core_url = urlparse(self.second_brain_core_url)
        if parsed_core_url.scheme not in {"http", "https"} or not parsed_core_url.netloc:
            raise ConfigError("SECOND_BRAIN_CORE_URL must be a valid http(s) URL.")

        if self.hermes_gateway_enabled:
            if not self.telegram_bot_token:
                raise ConfigError("TELEGRAM_BOT_TOKEN is required when Hermes gateway is enabled.")
            if not self.hermes_gateway_allowed_user_ids:
                raise ConfigError(
                    "HERMES_GATEWAY_ALLOWED_USER_IDS is required when Hermes gateway is enabled."
                )

        if self.is_production:
            if not self.authorized_telegram_user_ids:
                raise ConfigError("AUTHORIZED_TELEGRAM_USER_IDS is required in production.")
            if self.hermes_internal_tool_token in {"", "dev-token-change-me"}:
                raise ConfigError("HERMES_INTERNAL_TOOL_TOKEN must be changed in production.")
            if "tests/fixtures" in str(self.vault_path):
                raise ConfigError("Production cannot use the test vault fixture.")


def load_config(
    env: Mapping[str, str] | None = None,
    env_file: str | Path | None = ".env",
    project_root: str | Path | None = None,
) -> AppConfig:
    root = Path(project_root).resolve() if project_root else Path.cwd().resolve()
    file_values = _parse_env_file(root / Path(env_file)) if env_file else {}
    merged = dict(file_values)
    merged.update(dict(os.environ if env is None else env))

    user_ids = tuple(
        item.strip()
        for item in merged.get("AUTHORIZED_TELEGRAM_USER_IDS", "").split(",")
        if item.strip()
    )
    gateway_user_ids = tuple(
        item.strip()
        for item in merged.get("HERMES_GATEWAY_ALLOWED_USER_IDS", "").split(",")
        if item.strip()
    )

    config = AppConfig(
        app_env=merged.get("APP_ENV", "development"),
        authorized_telegram_user_ids=user_ids,
        vault_path=_as_path(merged.get("VAULT_PATH", "tests/fixtures/vault"), root),
        database_url=merged.get("DATABASE_URL", "sqlite:///./data/second_brain.dev.db"),
        attachment_temp_dir=_as_path(
            merged.get("ATTACHMENT_TEMP_DIR", "./data/tmp/attachments"), root
        ),
        log_level=merged.get("LOG_LEVEL", "INFO"),
        hermes_internal_tool_token=merged.get(
            "HERMES_INTERNAL_TOOL_TOKEN", "dev-token-change-me"
        ),
        telegram_bot_token=merged.get("TELEGRAM_BOT_TOKEN", ""),
        hermes_gateway_enabled=merged.get("HERMES_GATEWAY_ENABLED", "false").lower()
        in {"1", "true", "yes", "on"},
        hermes_gateway_allowed_user_ids=gateway_user_ids,
        second_brain_core_url=merged.get(
            "SECOND_BRAIN_CORE_URL", "http://127.0.0.1:8787"
        ),
        timezone=merged.get("TIMEZONE", "Asia/Jakarta"),
        vault_git_sync=merged.get("VAULT_GIT_SYNC", "false").lower()
        in {"1", "true", "yes", "on"},
        project_root=root,
    )
    config.validate()
    return config
