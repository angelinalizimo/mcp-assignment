"""
task_store.py
-------------
Core business logic for the Task Manager MCP server.

This module is intentionally kept independent of the `mcp` package so it can
be:
  1. Unit-tested / exploit-tested in isolation (no MCP protocol needed).
  2. Reused if the transport layer ever changes (stdio -> http, etc).

Security controls implemented here (see README.md for details):
  - Authentication: every mutating/read call requires a valid API token.
  - Best Practice #1 - Input Sanitization: all SQL uses parameterized
    queries; free-text fields are also validated (e.g. status is checked
    against a whitelist).
  - Best Practice #2 - Error Disclosure: internal exceptions (stack traces,
    file paths, SQL errors) are logged locally and NEVER returned to the
    caller. Callers only ever see a small set of generic, safe messages.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

# --------------------------------------------------------------------------
# Configuration / secrets
# --------------------------------------------------------------------------
DB_PATH = Path(os.getenv("TASK_DB_PATH", str(Path(__file__).parent / "tasks.db")))
API_TOKEN = os.getenv("API_TOKEN")

# --------------------------------------------------------------------------
# Logging: full detail goes to a local file ONLY.
# --------------------------------------------------------------------------
LOG_PATH = Path(__file__).parent / "server.log"
logger = logging.getLogger("task_store")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    file_handler = logging.FileHandler(LOG_PATH)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    )
    logger.addHandler(file_handler)

ALLOWED_STATUSES = {"all", "pending", "done"}
ALLOWED_PRIORITIES = {"low", "medium", "high"}


class AuthError(Exception):
    """Raised when the caller's token is missing or wrong."""


class ValidationError(Exception):
    """Raised when caller-supplied input fails validation."""


@contextmanager
def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                due_date TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
            """
        )


def _check_auth(auth_token: str) -> None:
    if not API_TOKEN:
        logger.error("Server misconfiguration: API_TOKEN is not set in the environment.")
        raise AuthError("Authentication is not available.")
    if not auth_token or auth_token != API_TOKEN:
        logger.warning("Authentication failed for a request (token mismatch or missing).")
        raise AuthError("Invalid or missing authentication token.")


def _validate_due_date(due_date: str) -> str:
    try:
        datetime.strptime(due_date, "%Y-%m-%d")
    except ValueError:
        raise ValidationError("due_date must be in YYYY-MM-DD format.")
    return due_date


def _validate_priority(priority: str) -> str:
    priority = priority.lower().strip()
    if priority not in ALLOWED_PRIORITIES:
        raise ValidationError(f"priority must be one of {sorted(ALLOWED_PRIORITIES)}.")
    return priority


def _validate_status(status: str) -> str:
    status = status.lower().strip()
    if status not in ALLOWED_STATUSES:
        raise ValidationError(f"status must be one of {sorted(ALLOWED_STATUSES)}.")
    return status


def _validate_title(title: str) -> str:
    title = title.strip()
    if not title:
        raise ValidationError("title cannot be empty.")
    if len(title) > 200:
        raise ValidationError("title cannot exceed 200 characters.")
    return title


def add_task(auth_token: str, title: str, due_date: str, priority: str = "medium") -> dict:
    """Insert a new task. Returns a plain dict (JSON-serializable)."""
    try:
        _check_auth(auth_token)
        title = _validate_title(title)
        due_date = _validate_due_date(due_date)
        priority = _validate_priority(priority)

        with _get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO tasks (title, due_date, priority, status, created_at) "
                "VALUES (?, ?, ?, 'pending', ?)",
                (title, due_date, priority, datetime.utcnow().isoformat()),
            )
            task_id = cur.lastrowid

        logger.info(f"Task created: id={task_id} title={title!r}")
        return {"success": True, "task_id": task_id, "title": title}

    except (AuthError, ValidationError) as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.exception(f"Unexpected error in add_task: {e}")
        return {"success": False, "error": "An internal error occurred. Please try again."}


def list_tasks(auth_token: str, status: str = "all") -> dict:
    """List tasks, optionally filtered by status."""
    try:
        _check_auth(auth_token)
        status = _validate_status(status)

        with _get_conn() as conn:
            if status == "all":
                rows = conn.execute(
                    "SELECT id, title, due_date, priority, status FROM tasks "
                    "ORDER BY due_date ASC"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, title, due_date, priority, status FROM tasks "
                    "WHERE status = ? ORDER BY due_date ASC",
                    (status,),
                ).fetchall()

        tasks = [
            {"id": r[0], "title": r[1], "due_date": r[2], "priority": r[3], "status": r[4]}
            for r in rows
        ]
        return {"success": True, "count": len(tasks), "tasks": tasks}

    except (AuthError, ValidationError) as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.exception(f"Unexpected error in list_tasks: {e}")
        return {"success": False, "error": "An internal error occurred. Please try again."}


init_db()