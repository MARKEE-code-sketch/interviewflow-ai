"""Configure terminal logging without printing third-party prompt/error bodies."""

import sys

from loguru import logger


def configure_logging():
    logger.remove()
    logger.add(
        sys.stderr, level="INFO", serialize=True, backtrace=False, diagnose=False,
        filter=lambda record: (record["name"] or "").startswith("interviewflow.")
        and bool(record["extra"].get("event")),
    )
