"""Small persistence boundary for interview setup handoff and final results."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from threading import Lock
from typing import Protocol

import psycopg
from dotenv import load_dotenv
from loguru import logger

from interviewflow.config import DEFAULT_ENV_FILE


class PersistenceError(RuntimeError):
    """Safe storage error that never contains credentials or interview content."""


class SessionPersistence(Protocol):
    def save_setup(self, setup_id: str, payload: dict, expires_at: float) -> None: ...
    def claim_setup(self, setup_id: str, now: float) -> dict | None: ...
    def save_result(self, session_id: str, payload: dict, expires_at: float) -> None: ...
    def get_result(self, session_id: str, now: float) -> dict | None: ...
    def healthcheck(self) -> bool: ...


def _encode(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _decode(value: str) -> dict:
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise PersistenceError("INTERVIEW_STORAGE_INVALID")
    return payload


class MemoryPersistence:
    """Fast isolated storage used by unit tests."""

    def __init__(self) -> None:
        self._setups: dict[str, tuple[dict, float]] = {}
        self._results: dict[str, tuple[dict, float]] = {}
        self._lock = Lock()

    def save_setup(self, setup_id: str, payload: dict, expires_at: float) -> None:
        with self._lock:
            self._setups[setup_id] = (payload, expires_at)

    def claim_setup(self, setup_id: str, now: float) -> dict | None:
        with self._lock:
            value = self._setups.pop(setup_id, None)
        if value is None or value[1] <= now:
            return None
        return value[0]

    def save_result(self, session_id: str, payload: dict, expires_at: float) -> None:
        with self._lock:
            self._results[session_id] = (payload, expires_at)

    def get_result(self, session_id: str, now: float) -> dict | None:
        with self._lock:
            value = self._results.get(session_id)
            if value is not None and value[1] <= now:
                self._results.pop(session_id, None)
                value = None
        return value[0] if value is not None else None

    def healthcheck(self) -> bool:
        return True


class SQLitePersistence:
    """Durable single-process local storage without an external service."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._initialize()

    def _connect(self):
        return sqlite3.connect(self._path, timeout=5)

    def _initialize(self) -> None:
        try:
            with self._connect() as connection:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS interview_setups (
                        setup_id TEXT PRIMARY KEY,
                        payload_json TEXT NOT NULL,
                        expires_at REAL NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS interview_results (
                        session_id TEXT PRIMARY KEY,
                        payload_json TEXT NOT NULL,
                        expires_at REAL NOT NULL
                    );
                    """
                )
        except sqlite3.Error as error:
            raise PersistenceError("INTERVIEW_STORAGE_UNAVAILABLE") from error

    def save_setup(self, setup_id: str, payload: dict, expires_at: float) -> None:
        try:
            with self._lock, self._connect() as connection:
                connection.execute(
                    "INSERT INTO interview_setups VALUES (?, ?, ?)",
                    (setup_id, _encode(payload), expires_at),
                )
        except (sqlite3.Error, TypeError, ValueError) as error:
            raise PersistenceError("INTERVIEW_STORAGE_WRITE_FAILED") from error

    def claim_setup(self, setup_id: str, now: float) -> dict | None:
        try:
            with self._lock, self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT payload_json FROM interview_setups "
                    "WHERE setup_id = ? AND expires_at > ?",
                    (setup_id, now),
                ).fetchone()
                connection.execute("DELETE FROM interview_setups WHERE setup_id = ?", (setup_id,))
            return _decode(row[0]) if row else None
        except (sqlite3.Error, json.JSONDecodeError) as error:
            raise PersistenceError("INTERVIEW_STORAGE_READ_FAILED") from error

    def save_result(self, session_id: str, payload: dict, expires_at: float) -> None:
        try:
            with self._lock, self._connect() as connection:
                connection.execute(
                    "INSERT INTO interview_results VALUES (?, ?, ?) "
                    "ON CONFLICT(session_id) DO UPDATE SET "
                    "payload_json = excluded.payload_json, expires_at = excluded.expires_at",
                    (session_id, _encode(payload), expires_at),
                )
        except (sqlite3.Error, TypeError, ValueError) as error:
            raise PersistenceError("INTERVIEW_STORAGE_WRITE_FAILED") from error

    def get_result(self, session_id: str, now: float) -> dict | None:
        try:
            with self._lock, self._connect() as connection:
                row = connection.execute(
                    "SELECT payload_json FROM interview_results "
                    "WHERE session_id = ? AND expires_at > ?",
                    (session_id, now),
                ).fetchone()
                connection.execute("DELETE FROM interview_results WHERE expires_at <= ?", (now,))
            return _decode(row[0]) if row else None
        except (sqlite3.Error, json.JSONDecodeError) as error:
            raise PersistenceError("INTERVIEW_STORAGE_READ_FAILED") from error

    def healthcheck(self) -> bool:
        try:
            with self._connect() as connection:
                return connection.execute("SELECT 1").fetchone() == (1,)
        except sqlite3.Error:
            return False


class PostgresPersistence:
    """Small PostgreSQL adapter for Render deployments and Neon storage."""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._initialize()

    def _connect(self):
        return psycopg.connect(self._database_url, connect_timeout=5)

    def _initialize(self) -> None:
        try:
            with self._connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS interview_setups (
                        setup_id TEXT PRIMARY KEY,
                        payload_json TEXT NOT NULL,
                        expires_at DOUBLE PRECISION NOT NULL
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS interview_results (
                        session_id TEXT PRIMARY KEY,
                        payload_json TEXT NOT NULL,
                        expires_at DOUBLE PRECISION NOT NULL
                    )
                    """
                )
        except psycopg.Error as error:
            raise PersistenceError("INTERVIEW_STORAGE_UNAVAILABLE") from error

    def save_setup(self, setup_id: str, payload: dict, expires_at: float) -> None:
        try:
            with self._connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO interview_setups VALUES (%s, %s, %s)",
                    (setup_id, _encode(payload), expires_at),
                )
        except (psycopg.Error, TypeError, ValueError) as error:
            raise PersistenceError("INTERVIEW_STORAGE_WRITE_FAILED") from error

    def claim_setup(self, setup_id: str, now: float) -> dict | None:
        try:
            with self._connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM interview_setups WHERE setup_id = %s AND expires_at > %s "
                    "RETURNING payload_json",
                    (setup_id, now),
                )
                row = cursor.fetchone()
                cursor.execute("DELETE FROM interview_setups WHERE expires_at <= %s", (now,))
            return _decode(row[0]) if row else None
        except (psycopg.Error, json.JSONDecodeError) as error:
            raise PersistenceError("INTERVIEW_STORAGE_READ_FAILED") from error

    def save_result(self, session_id: str, payload: dict, expires_at: float) -> None:
        try:
            with self._connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO interview_results VALUES (%s, %s, %s) "
                    "ON CONFLICT(session_id) DO UPDATE SET "
                    "payload_json = excluded.payload_json, expires_at = excluded.expires_at",
                    (session_id, _encode(payload), expires_at),
                )
        except (psycopg.Error, TypeError, ValueError) as error:
            raise PersistenceError("INTERVIEW_STORAGE_WRITE_FAILED") from error

    def get_result(self, session_id: str, now: float) -> dict | None:
        try:
            with self._connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT payload_json FROM interview_results "
                    "WHERE session_id = %s AND expires_at > %s",
                    (session_id, now),
                )
                row = cursor.fetchone()
                cursor.execute("DELETE FROM interview_results WHERE expires_at <= %s", (now,))
            return _decode(row[0]) if row else None
        except (psycopg.Error, json.JSONDecodeError) as error:
            raise PersistenceError("INTERVIEW_STORAGE_READ_FAILED") from error

    def healthcheck(self) -> bool:
        try:
            with self._connect() as connection, connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                return cursor.fetchone() == (1,)
        except psycopg.Error:
            return False


def create_session_persistence(env_file: Path = DEFAULT_ENV_FILE) -> SessionPersistence:
    """Use PostgreSQL when configured; otherwise keep local data in SQLite."""

    load_dotenv(env_file, override=False)
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        backend: SessionPersistence = PostgresPersistence(database_url)
        backend_name = "postgres"
    else:
        path = Path(os.getenv("SQLITE_PATH", "data/interviewflow.db"))
        backend = SQLitePersistence(path)
        backend_name = "sqlite"
    logger.bind(event="interview_storage_ready", backend=backend_name).info(
        "Interview storage ready"
    )
    return backend
