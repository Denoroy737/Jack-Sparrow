"""Configuration loading and validation.

Values come from the process environment. A `.env` file in the working
directory is read as a fallback for names that are not already set.
Secrets are never printed or logged (Rules R9, R12).
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

ENV_FILE = ".env"

SECRET_FIELDS = (
    "TELEGRAM_BOT_TOKEN",
    "GROQ_API_KEY",
    "GEMINI_API_KEY",
    "NOTION_TOKEN",
    "EXA_API_KEY",
)


class ConfigError(ValueError):
    """Raised when configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str | None = None
    telegram_owner_id: int | None = None
    groq_api_key: str | None = None
    gemini_api_key: str | None = None
    exa_api_key: str | None = None
    notion_token: str | None = None
    notion_database_id: str | None = None
    notion_parent_page_id: str | None = None
    data_dir: Path = Path("./data")
    groq_chat_model: str | None = None
    log_level: str = "INFO"
    extra: dict[str, str] = field(default_factory=dict, repr=False)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "jack_sparrow.db"

    @property
    def media_dir(self) -> Path:
        return self.data_dir / "media"


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse KEY=VALUE lines. Ignores blank lines and comments. Strips optional quotes."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        values[key.strip()] = value
    return values


def load_config(
    environ: Mapping[str, str] | None = None,
    env_file: Path | None = None,
) -> Config:
    """Build a Config from the environment, falling back to the .env file.

    Raises ConfigError only for values that are present but malformed.
    Missing values are allowed here; use `require()` at the point of use.
    """
    env = dict(os.environ if environ is None else environ)
    file_values = parse_env_file(env_file or Path(ENV_FILE))
    for key, value in file_values.items():
        env.setdefault(key, value)

    owner_raw = env.get("TELEGRAM_OWNER_ID")
    owner_id: int | None = None
    if owner_raw:
        try:
            owner_id = int(owner_raw)
        except ValueError as exc:
            raise ConfigError("TELEGRAM_OWNER_ID must be a whole number") from exc

    log_level = env.get("JACK_SPARROW_LOG_LEVEL", "INFO").upper()
    if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
        raise ConfigError("JACK_SPARROW_LOG_LEVEL must be DEBUG, INFO, WARNING, or ERROR")

    return Config(
        telegram_bot_token=env.get("TELEGRAM_BOT_TOKEN") or None,
        telegram_owner_id=owner_id,
        groq_api_key=env.get("GROQ_API_KEY") or None,
        gemini_api_key=env.get("GEMINI_API_KEY") or None,
        exa_api_key=env.get("EXA_API_KEY") or None,
        notion_token=env.get("NOTION_TOKEN") or None,
        notion_database_id=env.get("NOTION_DATABASE_ID") or None,
        notion_parent_page_id=env.get("NOTION_PARENT_PAGE_ID") or None,
        data_dir=Path(env.get("JACK_SPARROW_DATA_DIR", "./data")),
        groq_chat_model=env.get("JACK_SPARROW_GROQ_CHAT_MODEL") or None,
        log_level=log_level,
        extra={k: v for k, v in env.items() if k.startswith("JACK_SPARROW_")},
    )


def missing(config: Config, names: Iterable[str]) -> list[str]:
    """Return the env-style names whose values are not set on this config."""
    attr_for = {
        "TELEGRAM_BOT_TOKEN": "telegram_bot_token",
        "TELEGRAM_OWNER_ID": "telegram_owner_id",
        "GROQ_API_KEY": "groq_api_key",
        "GEMINI_API_KEY": "gemini_api_key",
        "EXA_API_KEY": "exa_api_key",
        "NOTION_TOKEN": "notion_token",
        "NOTION_DATABASE_ID": "notion_database_id",
        "NOTION_PARENT_PAGE_ID": "notion_parent_page_id",
    }
    result = []
    for name in names:
        attr = attr_for.get(name)
        if attr is None:
            raise ConfigError(f"Unknown config name: {name}")
        if getattr(config, attr) in (None, ""):
            result.append(name)
    return result


def require(config: Config, names: Iterable[str]) -> None:
    """Raise ConfigError listing every missing name. Never includes values."""
    absent = missing(config, list(names))
    if absent:
        raise ConfigError("Missing required settings: " + ", ".join(absent))
