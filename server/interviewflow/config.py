"""Small, provider-neutral application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"


@dataclass(frozen=True)
class AppSettings:
    """Settings required before any AI providers are selected."""

    environment: str
    interview_duration_minutes: int


def load_settings(env_file: Path = DEFAULT_ENV_FILE) -> AppSettings:
    """Load local settings and reject an invalid interview duration."""

    load_dotenv(dotenv_path=env_file, override=False)

    raw_duration = os.getenv("INTERVIEW_DURATION_MINUTES", "15")
    try:
        duration = int(raw_duration)
    except ValueError as error:
        raise ValueError("INTERVIEW_DURATION_MINUTES must be a whole number") from error

    if duration <= 0:
        raise ValueError("INTERVIEW_DURATION_MINUTES must be greater than zero")

    return AppSettings(
        environment=os.getenv("APP_ENV", "development"),
        interview_duration_minutes=duration,
    )

