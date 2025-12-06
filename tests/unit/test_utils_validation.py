#!/usr/bin/env python3
"""
Validation test for shared utilities.

Tests logger, database, and their integration.
Run with: PYTHONPATH=. python tests/test_utils_validation.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.logger import get_logger
from src.utils.database import get_connection, init_test_db, cleanup_test_db, get_db_path


def test_logger():
    """Test unified logging."""
    print("\n=== Testing Logger ===")

    logger = get_logger("test_utils")

    logger.info("Testing INFO level logging")
    logger.warning("Testing WARNING level logging")
    logger.error("Testing ERROR level logging")

    print("\nCheck logs/workflow.log for these entries")
    return True


def test_database():
    """Test database utilities."""
    print("\n=== Testing Database ===")

    logger = get_logger("test_database")

    # Initialize test DB
    logger.info("Initializing test database")
    init_test_db()

    test_db_path = get_db_path(test_mode=True)
    logger.info(f"Test DB created at: {test_db_path}")

    if not test_db_path.exists():
        logger.error("Test DB was not created!")
        return False

    # Get connection and verify schema
    logger.info("Verifying schema...")
    conn = get_connection(test_mode=True)
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]

    expected_tables = ['papers', 'citations', 'authors', 'paper_authors']
    for table in expected_tables:
        if table in tables:
            logger.info(f"  Table '{table}' exists")
        else:
            logger.error(f"  Table '{table}' missing!")
            return False

    # Test insert
    logger.info("Testing data insertion...")
    cursor.execute("""
        INSERT INTO papers (pmid, title, pub_year, fetch_date)
        VALUES (99999, 'Test Paper', 2025, '2025-12-05')
    """)
    conn.commit()

    # Verify insert
    cursor.execute("SELECT COUNT(*) FROM papers")
    count = cursor.fetchone()[0]
    logger.info(f"  Inserted test paper (count: {count})")

    conn.close()

    # Cleanup
    logger.info("Cleaning up test database")
    cleanup_test_db()

    if test_db_path.exists():
        logger.error("Test DB was not cleaned up!")
        return False

    logger.info("  Test DB cleaned up successfully")

    return True


def test_production_db_access():
    """Test production DB access (read-only)."""
    print("\n=== Testing Production DB Access ===")

    logger = get_logger("test_production")

    prod_db_path = get_db_path(test_mode=False)
    logger.info(f"Production DB path: {prod_db_path}")

    if not prod_db_path.exists():
        logger.warning("Production DB doesn't exist yet (this is OK for new projects)")
        return True

    # Read-only test
    logger.info("Testing read access...")
    conn = get_connection(test_mode=False)
    cursor = conn.execute("SELECT COUNT(*) FROM papers")
    count = cursor.fetchone()[0]
    logger.info(f"  Production DB has {count} papers")
    conn.close()

    return True


def main():
    """Run all validation tests."""
    print("="*60)
    print("UTILITIES VALIDATION TEST")
    print("="*60)

    results = []

    # Test logger
    results.append(("Logger", test_logger()))

    # Test database
    results.append(("Database", test_database()))

    # Test production access
    results.append(("Production Access", test_production_db_access()))

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    for test_name, passed in results:
        status = "OK PASS" if passed else "ERROR FAIL"
        print(f"{test_name:20} {status}")

    all_passed = all(result for _, result in results)

    if all_passed:
        print("\nOK All tests passed!")
        print("\nNext steps:")
        print("1. Check logs/workflow.log for log entries")
        print("2. Utilities are ready to use in pipeline refactor")
        return 0
    else:
        print("\nERROR Some tests failed. Check output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
