"""Entry point.

    python -m app        create or upgrade the local database, then exit
    python -m app bot    run the Telegram bot (long polling)
    python -m app text-report FILE   analyze a text file and save it as a report
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

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
    analyzer = build_analyzer(config.groq_api_key, config.exa_api_key, config.groq_chat_model)
    publisher = None
    if config.notion_token:
        from app.notion_client import NotionClient, NotionError
        from app.notion_publish import build_publisher, check_database
        from app.notion_setup import NotionSetupError, ensure_database
        from app.notion_writer import NotionSchemaError

        client = NotionClient(config.notion_token)
        try:
            database_id = ensure_database(
                client, config.data_dir, config.notion_database_id, config.notion_parent_page_id
            )
            check_database(config.notion_token, database_id)
        except (NotionSetupError, NotionSchemaError) as exc:
            print(f"Notion setup error: {exc}", file=sys.stderr)
            return 2
        except NotionError as exc:
            print(f"Notion request failed: {exc}", file=sys.stderr)
            return 2
        log.info("Notion database ready (id saved in %s)", config.data_dir)
        publisher = build_publisher(config.notion_token, database_id)
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


def run_groq_check(config: Config) -> int:
    """Lists the chat models this key can use, then tries one JSON call. Prints no secrets."""
    require(config, ["GROQ_API_KEY"])
    from groq import Groq

    client = Groq(api_key=config.groq_api_key, timeout=60.0)
    try:
        models = sorted(m.id for m in client.models.list().data)
    except Exception as exc:  # noqa: BLE001
        print(f"Could not list models: {type(exc).__name__} "
              f"(status {getattr(exc, 'status_code', 'n/a')})", file=sys.stderr)
        return 2
    print(f"{len(models)} models available to this key:")
    for model_id in models:
        print(f"  {model_id}")
    model = config.groq_chat_model or "llama-3.3-70b-versatile"
    print(f"\nTesting chat model: {model}")
    try:
        client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with the JSON object {\"ok\": true}."}],
            response_format={"type": "json_object"},
        )
        print("chat call: OK")
    except Exception as exc:  # noqa: BLE001
        status = getattr(exc, "status_code", "n/a")
        print(f"chat call failed: {type(exc).__name__} (status {status})")
        print("Set JACK_SPARROW_GROQ_CHAT_MODEL in .env to one of the models listed above.")
        return 2
    return 0


def run_text_report(config: Config, path: Path) -> int:
    """Analyze a plain text file (for example a post) and save it like a reel report."""
    require(config, ["GROQ_API_KEY"])
    _prepare(config)
    from hashlib import sha256

    from app.analysis import build_analyzer
    from app.context import ReelContext
    from app.transcribe import Transcript

    text = path.read_text(encoding="utf-8").strip()
    if len(text) < 20:
        print("The text file is too short to report on.", file=sys.stderr)
        return 2
    analyzer = build_analyzer(config.groq_api_key, config.exa_api_key, config.groq_chat_model)
    report = analyzer(Transcript(text, "en", (), "text-input"), "text input", ReelContext())

    job_id = "text-" + sha256(text.encode("utf-8")).hexdigest()[:12]
    out_dir = config.data_dir / "text-reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{job_id}.json"
    out_file.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    print(f"Report: {report.title} (saved to {out_file})")

    if not config.notion_token:
        print("NOTION_TOKEN is not set, so nothing was saved to Notion.")
        return 0
    from app.notion_client import NotionClient, NotionError
    from app.notion_publish import build_publisher
    from app.notion_setup import NotionSetupError, ensure_database
    from app.notion_writer import NotionSchemaError

    try:
        database_id = ensure_database(
            NotionClient(config.notion_token), config.data_dir,
            config.notion_database_id, config.notion_parent_page_id,
        )
    except (NotionSetupError, NotionSchemaError, NotionError) as exc:
        print(f"Notion setup error: {exc}", file=sys.stderr)
        return 2
    page_id, page_url = build_publisher(config.notion_token, database_id)(job_id, report, text)
    print(f"Saved to Notion: {page_url or page_id}")
    return 0


def main(argv: list[str]) -> int:
    try:
        config = load_config()
        if len(argv) > 1 and argv[1] == "bot":
            return run_bot(config)
        if len(argv) > 1 and argv[1] == "notion-check":
            return run_notion_check(config)
        if len(argv) > 1 and argv[1] == "groq-check":
            return run_groq_check(config)
        if len(argv) > 2 and argv[1] == "text-report":
            return run_text_report(config, Path(argv[2]))
        return run_db_only(config)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
