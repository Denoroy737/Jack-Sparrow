from pathlib import Path

import pytest

from app.config import ConfigError, load_config, missing, parse_env_file, require


def test_loads_values_from_environment(tmp_path: Path) -> None:
    env = {
        "TELEGRAM_BOT_TOKEN": "tok",
        "TELEGRAM_OWNER_ID": "42",
        "JACK_SPARROW_DATA_DIR": str(tmp_path / "d"),
    }
    cfg = load_config(environ=env, env_file=tmp_path / "none.env")
    assert cfg.telegram_bot_token == "tok"
    assert cfg.telegram_owner_id == 42
    assert cfg.data_dir == tmp_path / "d"


def test_env_file_fills_gaps_but_does_not_override(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text('GROQ_API_KEY="from-file"\nTELEGRAM_OWNER_ID=7\n', encoding="utf-8")
    cfg = load_config(environ={"TELEGRAM_OWNER_ID": "99"}, env_file=env_file)
    assert cfg.groq_api_key == "from-file"
    assert cfg.telegram_owner_id == 99


def test_non_numeric_owner_id_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="whole number"):
        load_config(environ={"TELEGRAM_OWNER_ID": "abc"}, env_file=tmp_path / "x")


def test_bad_log_level_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="LOG_LEVEL"):
        load_config(environ={"JACK_SPARROW_LOG_LEVEL": "LOUD"}, env_file=tmp_path / "x")


def test_require_lists_names_without_values(tmp_path: Path) -> None:
    cfg = load_config(environ={"GROQ_API_KEY": "super-secret"}, env_file=tmp_path / "x")
    with pytest.raises(ConfigError) as info:
        require(cfg, ["GROQ_API_KEY", "NOTION_TOKEN"])
    message = str(info.value)
    assert "NOTION_TOKEN" in message
    assert "super-secret" not in message
    assert "GROQ_API_KEY" not in message.split(":")[-1]


def test_missing_reports_unset_names(tmp_path: Path) -> None:
    cfg = load_config(environ={}, env_file=tmp_path / "x")
    assert missing(cfg, ["TELEGRAM_BOT_TOKEN"]) == ["TELEGRAM_BOT_TOKEN"]


def test_parse_env_file_skips_comments_and_blanks(tmp_path: Path) -> None:
    f = tmp_path / ".env"
    f.write_text("# comment\n\nA=1\nB='two'\n", encoding="utf-8")
    assert parse_env_file(f) == {"A": "1", "B": "two"}


def test_parse_env_file_missing_returns_empty(tmp_path: Path) -> None:
    assert parse_env_file(tmp_path / "nope.env") == {}
