from pathlib import Path

from interviewflow.persistence import SQLitePersistence, create_session_persistence


def test_sqlite_setup_survives_restart_and_can_be_claimed_once(tmp_path: Path):
    database = tmp_path / "interviews.db"
    first_process = SQLitePersistence(database)
    first_process.save_setup("setup-1", {"page_count": 2}, expires_at=200)

    restarted_process = SQLitePersistence(database)
    assert restarted_process.claim_setup("setup-1", now=100) == {"page_count": 2}
    assert restarted_process.claim_setup("setup-1", now=100) is None


def test_sqlite_expired_setup_and_result_are_not_returned(tmp_path: Path):
    storage = SQLitePersistence(tmp_path / "interviews.db")
    storage.save_setup("expired-setup", {"private": "text"}, expires_at=10)
    storage.save_result("expired-result", {"status": "complete"}, expires_at=10)

    assert storage.claim_setup("expired-setup", now=10) is None
    assert storage.get_result("expired-result", now=10) is None


def test_sqlite_result_survives_restart_and_healthcheck_passes(tmp_path: Path):
    database = tmp_path / "interviews.db"
    SQLitePersistence(database).save_result(
        "session-1", {"status": "complete", "scorecard": {"overall_score": 80}}, 200
    )

    restarted_process = SQLitePersistence(database)
    assert restarted_process.get_result("session-1", now=100) == {
        "status": "complete",
        "scorecard": {"overall_score": 80},
    }
    assert restarted_process.healthcheck() is True


def test_factory_uses_configured_sqlite_path(monkeypatch, tmp_path: Path):
    database = tmp_path / "configured.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("SQLITE_PATH", str(database))

    storage = create_session_persistence(tmp_path / "missing.env")

    assert isinstance(storage, SQLitePersistence)
    assert database.exists()
