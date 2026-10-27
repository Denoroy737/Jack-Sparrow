"""Entry point.

    python -m app        create or upgrade the local database, then exit
    python -m app bot    run the Telegram bot (long polling)
"""

from __future__ import annotations

import asyncio
import logging
import sys

from app.config import Config, ConfigError, load_config, require
from app.logging_setup import setup_logging
from app.store import init_db


def _prepare(config: Config) -> logging.Logger:
    setup_logging(config.log_level)
    config.data_dir.mkdir(parents=True, exist_ok=True)
    init_db(config.db_path)
    return logging.getLogger("jack_sparrow")


def run_db_only(config: Config) -> int:
    log = _prepare(config)
    log.info("database ready at %s", config.db_path)
    return 0


def run_bot(config: Config) -> int:
    require(config, ["TELEGRAM_BOT_TOKEN", "TELEGRAM_OWNER_ID"])
    log = _prepare(config)

    from app.analysis import build_analyzer
    from app.bot import run_polling
    from app.intake import Intake
    from app.transcribe import build_transcriber

    intake = Intake(db_path=config.db_path, owner_id=config.telegram_owner_id or 0)
    transcriber = build_transcriber(config.groq_api_key)
    analyzer = build_analyzer(config.groq_api_key, config.exa_api_key)
    publisher = None
    if config.notion_token and config.notion_database_id:
        from app.notion_publish import build_publisher, check_database
        from app.notion_writer import NotionSchemaError

        try:
            check_database(config.notion_token, config.notion_database_id)
        except NotionSchemaError as exc:
            print(f"Notion setup error: {exc}", file=sys.stderr)
            return 2
        except Exception as exc:  # noqa: BLE001
            print(f"Notion check failed: {type(exc).__name__}", file=sys.stderr)
            return 2
        publisher = build_publisher(config.notion_token, config.notion_database_id)
    try:
        asyncio.run(
            run_polling(
                config.telegram_bot_token or "",
                intake,
                data_dir=config.data_dir,
                transcriber=transcriber,
                analyze=analyzer,
                publish=publisher,
            )
        )
    except KeyboardInterrupt:
        log.info("bot stopped")
    return 0


def run_notion_check(config: Config) -> int:
    require(config, ["NOTION_TOKEN", "NOTION_DATABASE_ID"])
    from app.notion_check import describe_database
    from app.notion_client import NotionClient, NotionError

    try:
        client = NotionClient(config.notion_token or "")
        lines = describe_database(client, config.notion_database_id or "")
    except NotionError as exc:
        print(f"Notion request failed: {exc}", file=sys.stderr)
        return 2
    print("\n".join(lines))
    return 0


def main(argv: list[str]) -> int:
    try:
        config = load_config()
        if len(argv) > 1 and argv[1] == "bot":
            return run_bot(config)
        if len(argv) > 1 and argv[1] == "notion-check":
            return run_notion_check(config)
        return run_db_only(config)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
