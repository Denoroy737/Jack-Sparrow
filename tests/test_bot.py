from pathlib import Path

from app.bot import build_dispatcher
from app.intake import Intake
from app.store import init_db


def test_dispatcher_wires_intake_and_db_path(tmp_path: Path) -> None:
    db = tmp_path / "jobs.db"
    init_db(db)
    intake = Intake(db_path=db, owner_id=1)
    dp = build_dispatcher(intake)
    assert dp["intake"] is intake
    assert dp["db_path"] == db
