import json
from typing import Any

import pytest

from app.notion_client import NotionClient
from app.notion_writer import (
    NotionSchemaError,
    build_properties,
    schema_problems,
    validate_database,
    write_report,
)
from app.schemas import Report

GOOD_DB = {"properties": {
    "Title": {"type": "title"},
    "Category": {"type": "select"},
    "Tags": {"type": "multi_select"},
    "Source URL": {"type": "url"},
    "Creator": {"type": "rich_text"},
    "Date saved": {"type": "date"},
    "Status": {"type": "select"},
    "Confidence": {"type": "select"},
    "Job ID": {"type": "rich_text"},
}}


def make_report(**overrides: Any) -> Report:
    base = dict(
        title="A useful reel", category="coding", tags=["python", "bot"],
        source_url="https://www.instagram.com/reel/A/", creator=None,
        tldr="Short summary that is long enough.", key_points=["one"], steps=[], tools=[],
        links=[], claims=[], papers=[], chart=None, open_questions=[], confidence="high",
    )
    base.update(overrides)
    return Report(**base)


class FakeClient:
    def __init__(self, database=GOOD_DB, existing_page=None):
        self.database = database
        self.existing_page = existing_page
        self.calls: list[tuple[str, str, Any]] = []

    def retrieve_database(self, database_id):
        self.calls.append(("retrieve", database_id, None))
        return self.database

    def query_database(self, database_id, body):
        self.calls.append(("query", database_id, body))
        return {"results": [{"id": self.existing_page}] if self.existing_page else []}

    def create_page(self, body):
        self.calls.append(("create", "", body))
        return {"id": "new-page"}

    def update_page(self, page_id, body):
        self.calls.append(("update", page_id, body))
        return {"id": page_id}


def test_valid_schema_has_no_problems() -> None:
    assert schema_problems(GOOD_DB) == []


def test_missing_and_wrong_properties_are_listed() -> None:
    db = {"properties": {"Title": {"type": "rich_text"}, "Category": {"type": "select"}}}
    problems = schema_problems(db)
    assert "'Title' must be type title" in problems
    assert any("missing property 'Tags'" == p for p in problems)


def test_validate_database_raises_with_all_problems() -> None:
    with pytest.raises(NotionSchemaError) as info:
        validate_database(FakeClient(database={"properties": {}}), "db")
    assert "Job ID" in str(info.value)


def test_properties_map_report_fields() -> None:
    props = build_properties(make_report(creator="@maker"), "job-1", "2026-10-28", "Ready")
    assert props["Title"]["title"][0]["text"]["content"] == "A useful reel"
    assert props["Category"] == {"select": {"name": "coding"}}
    assert props["Job ID"]["rich_text"][0]["text"]["content"] == "job-1"
    assert props["Creator"]["rich_text"][0]["text"]["content"] == "@maker"


def test_new_report_creates_one_page() -> None:
    client = FakeClient(existing_page=None)
    page_id, _url = write_report(client, "db", make_report(), "job-1", "2026-10-28", "speech")
    assert page_id == "new-page"
    assert [c[0] for c in client.calls] == ["query", "create"]
    assert "children" in client.calls[-1][2]


def test_same_job_updates_instead_of_duplicating() -> None:
    client = FakeClient(existing_page="old-page")
    page_id, _url = write_report(client, "db", make_report(), "job-1", "2026-10-28", "speech")
    assert page_id == "old-page"
    assert [c[0] for c in client.calls] == ["query", "update"]
    assert "children" not in client.calls[-1][2]  # body is never rewritten on rerun


def test_notion_errors_do_not_leak_token() -> None:
    client = NotionClient("secret_TOKEN_123")

    def boom(*a, **k):
        raise RuntimeError("network down")

    import app.notion_client as nc

    original = nc.urllib.request.urlopen
    nc.urllib.request.urlopen = boom
    try:
        with pytest.raises(Exception) as info:
            client.retrieve_database("db")
        assert "secret_TOKEN_123" not in str(info.value)
    finally:
        nc.urllib.request.urlopen = original


def test_json_round_trip_of_properties() -> None:
    props = build_properties(make_report(), "job-1", "2026-10-28", "Ready")
    assert json.loads(json.dumps(props)) == props
