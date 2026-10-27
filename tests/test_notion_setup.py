from pathlib import Path

import pytest

from app.notion_setup import NotionSetupError, ensure_database, find_parent_page
from app.notion_writer import REQUIRED_PROPERTIES


class FakeClient:
    def __init__(self, pages=None):
        self.pages = pages or []
        self.created = []

    def request(self, method, path, body=None):
        if path == "/search":
            return {"results": self.pages}
        if path == "/databases":
            self.created.append(body)
            return {"id": "new-db-id"}
        raise AssertionError(path)


def test_creates_database_with_all_required_properties(tmp_path: Path) -> None:
    client = FakeClient(pages=[{"id": "page-1"}])
    db_id = ensure_database(client, tmp_path, None, None)
    assert db_id == "new-db-id"
    body = client.created[0]
    assert body["parent"] == {"type": "page_id", "page_id": "page-1"}
    assert set(body["properties"]) == set(REQUIRED_PROPERTIES)
    assert (tmp_path / "notion_database_id.txt").read_text(encoding="utf-8") == "new-db-id"


def test_reuses_saved_database_id(tmp_path: Path) -> None:
    (tmp_path / "notion_database_id.txt").write_text("saved-id", encoding="utf-8")
    client = FakeClient(pages=[{"id": "page-1"}])
    assert ensure_database(client, tmp_path, None, None) == "saved-id"
    assert client.created == []


def test_configured_database_id_wins(tmp_path: Path) -> None:
    client = FakeClient()
    assert ensure_database(client, tmp_path, "mine", None) == "mine"
    assert client.created == []


def test_no_shared_page_gives_clear_error() -> None:
    with pytest.raises(NotionSetupError, match="No Notion page is shared"):
        find_parent_page(FakeClient(pages=[]))


def test_several_shared_pages_asks_for_parent_id() -> None:
    with pytest.raises(NotionSetupError, match="NOTION_PARENT_PAGE_ID"):
        find_parent_page(FakeClient(pages=[{"id": "a"}, {"id": "b"}]))


def test_configured_parent_page_is_used_directly() -> None:
    assert find_parent_page(FakeClient(pages=[]), "chosen") == "chosen"
