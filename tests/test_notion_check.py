import pytest

from app.notion_check import describe_database
from app.notion_writer import NotionSchemaError, validate_database


class FakeClient:
    def __init__(self, db):
        self.db = db

    def retrieve_database(self, database_id):
        return self.db


def test_reports_properties_and_ok_schema() -> None:
    props = {
        "Title": "title", "Category": "select", "Tags": "multi_select",
        "Source URL": "url", "Creator": "rich_text", "Date saved": "date",
        "Status": "select", "Confidence": "select", "Job ID": "rich_text",
    }
    db = {
        "object": "database",
        "title": [{"plain_text": "Maya"}],
        "properties": {name: {"type": kind} for name, kind in props.items()},
    }
    lines = describe_database(FakeClient(db), "x")
    assert "schema: OK" in lines
    assert "name: Maya" in lines


def test_page_id_gets_a_hint() -> None:
    lines = describe_database(FakeClient({"object": "page"}), "x")
    assert any("does not point to a database" in line for line in lines)


def test_empty_properties_gets_connection_hint() -> None:
    lines = describe_database(FakeClient({"object": "database", "properties": {}}), "x")
    assert any("integration is connected" in line for line in lines)


def test_validate_explains_empty_response() -> None:
    with pytest.raises(NotionSchemaError) as info:
        validate_database(FakeClient({"object": "database", "properties": {}}), "x")
    assert "no properties" in str(info.value)
