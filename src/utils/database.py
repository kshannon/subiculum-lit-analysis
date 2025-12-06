"""
Standardized database access for the entire project.
Provides consistent DB paths and connection utilities with test mode isolation.
"""

import sqlite3
from pathlib import Path
from typing import Optional


# Standardized paths for entire project
PROJECT_ROOT = Path(__file__).parent.parent.parent
DB_PATH = PROJECT_ROOT / "data" / "raw" / "subiculum_literature.db"
TEST_DB_PATH = PROJECT_ROOT / "data" / "test" / "test.db"
SCHEMA_PATH = PROJECT_ROOT / "data" / "raw" / "schema.sql"


def get_connection(test_mode: bool = False) -> sqlite3.Connection:
    """
    Get database connection with standardized configuration.

    Args:
        test_mode: If True, uses test.db instead of production DB

    Returns:
        SQLite connection with foreign keys enabled
    """
    db_path = TEST_DB_PATH if test_mode else DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


def init_test_db() -> None:
    """
    Initialize test.db with schema for testing.
    Safe to call multiple times. Never affects production database.
    """
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

    TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(test_mode=True)

    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Schema not found at {SCHEMA_PATH}")

    with open(SCHEMA_PATH) as f:
        schema_sql = f.read()
        conn.executescript(schema_sql)

    conn.commit()
    conn.close()


def cleanup_test_db() -> None:
    """Remove test.db after testing."""
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


def get_db_path(test_mode: bool = False) -> Path:
    """Get the standardized database path."""
    return TEST_DB_PATH if test_mode else DB_PATH
