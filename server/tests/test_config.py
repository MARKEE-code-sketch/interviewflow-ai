from pathlib import Path

import pytest

from interviewflow import __version__
from interviewflow.config import load_settings


def test_package_imports() -> None:
    assert __version__ == "0.1.0"


def test_settings_have_safe_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("INTERVIEW_DURATION_MINUTES", raising=False)

    settings = load_settings(tmp_path / "missing.env")

    assert settings.environment == "development"
    assert settings.interview_duration_minutes == 15


def test_settings_load_from_env_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("INTERVIEW_DURATION_MINUTES", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "APP_ENV=test\nINTERVIEW_DURATION_MINUTES=10\n",
        encoding="utf-8",
    )

    settings = load_settings(env_file)

    assert settings.environment == "test"
    assert settings.interview_duration_minutes == 10


@pytest.mark.parametrize("value", ["0", "-1", "fifteen"])
def test_invalid_duration_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    value: str,
) -> None:
    monkeypatch.setenv("INTERVIEW_DURATION_MINUTES", value)

    with pytest.raises(ValueError, match="INTERVIEW_DURATION_MINUTES"):
        load_settings(tmp_path / "missing.env")
