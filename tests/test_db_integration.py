#!/usr/bin/env python3
"""
Integration Test #3: Database Integration

Tests complete ETL cycle: Parse XML -> Insert into DB -> Verify data.
Uses test database that is deleted after test completes.
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from transform.xml_parser import parse_xml_batch
from load.db_writer import DatabaseWriter


def test_database_integration():
    print("\n=== Testing Database Integration ===\n")
    print("Step 1: Creating test database...")
    test_db_path = Path(__file__).parent.parent / "data" / "test_integration.db"

    if test_db_path.exists():
        test_db_path.unlink()

    schema_path = Path(__file__).parent.parent / "data" / "schema.sql"
    with open(schema_path, "r") as f:
        schema_sql = f.read()

    conn = sqlite3.connect(str(test_db_path))
    conn.executescript(schema_sql)
    conn.close()
    print("  ✓ Test database created with schema")
    print("\nStep 2: Loading and parsing XML fixture...")
    fixture_path = Path(__file__).parent.parent / "data" / "test" / "pubmed_api_test.xml"

    with open(fixture_path, "r") as f:
        xml_data = f.read()

    papers = parse_xml_batch(xml_data)
    print(f"  ✓ Parsed {len(papers)} papers from fixture")
    print("\nStep 3: Inserting papers into database...")

    with DatabaseWriter(str(test_db_path)) as writer:
        success_count = 0
        for paper in papers:
            if writer.insert_paper(paper):
                success_count += 1

    print(f"  ✓ Inserted {success_count}/{len(papers)} papers successfully")
    assert success_count == len(papers), f"Expected {len(papers)} successful inserts, got {success_count}"

    print("\nStep 4: Verifying data in database...")
    conn = sqlite3.connect(str(test_db_path))
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM papers")
    paper_count = cursor.fetchone()[0]
    print(f"  ✓ Papers in DB: {paper_count}")
    assert paper_count == len(papers), f"Expected {len(papers)} papers, found {paper_count}"

    cursor.execute("SELECT COUNT(*) FROM authors")
    author_count = cursor.fetchone()[0]
    print(f"  ✓ Authors in DB: {author_count}")
    assert author_count > 0, "Should have at least 1 author"

    cursor.execute("SELECT COUNT(*) FROM paper_authors")
    paper_author_count = cursor.fetchone()[0]
    print(f"  ✓ Paper-author links: {paper_author_count}")
    assert paper_author_count > 0, "Should have at least 1 paper-author link"

    cursor.execute("SELECT COUNT(*) FROM citations")
    citation_count = cursor.fetchone()[0]
    print(f"  ✓ Citations in DB: {citation_count}")

    cursor.execute("SELECT COUNT(*) FROM fetch_log WHERE fetch_success = 1")
    fetch_log_count = cursor.fetchone()[0]
    print(f"  ✓ Successful fetch_log entries: {fetch_log_count}")
    assert fetch_log_count == len(papers), f"Expected {len(papers)} fetch_log entries, found {fetch_log_count}"

    print("\nStep 5: Verifying foreign key constraints...")

    cursor.execute("""
        SELECT COUNT(*) FROM paper_authors pa
        LEFT JOIN papers p ON pa.pmid = p.pmid
        WHERE p.pmid IS NULL
    """)
    orphaned = cursor.fetchone()[0]
    assert orphaned == 0, "Found orphaned paper_authors"
    print("  ✓ No orphaned paper-author links")

    cursor.execute("""
        SELECT COUNT(*) FROM paper_authors pa
        LEFT JOIN authors a ON pa.author_id = a.author_id
        WHERE a.author_id IS NULL
    """)
    orphaned = cursor.fetchone()[0]
    assert orphaned == 0, "Found orphaned author references"
    print("  ✓ No orphaned author references")
    print("\nStep 6: Testing PRIMARY KEY constraint...")
    cursor.execute("SELECT pmid, author_id FROM paper_authors LIMIT 1")
    test_row = cursor.fetchone()

    if test_row:
        try:
            # Try to insert duplicate (pmid, author_id) with different position
            cursor.execute("""
                INSERT INTO paper_authors (pmid, author_id, author_position, affiliation)
                VALUES (?, ?, 999, 'Test')
            """, test_row)
            conn.commit()
            assert False, "Should have failed PK constraint"
        except sqlite3.IntegrityError as e:
            print(f"  ✓ PRIMARY KEY enforced: {e}")
            conn.rollback()

    print("\nStep 7: Testing UNIQUE constraint...")
    cursor.execute("SELECT pmid, author_position FROM paper_authors LIMIT 1")
    test_row = cursor.fetchone()

    if test_row:
        try:
            # Try to insert different author at same position
            cursor.execute("""
                INSERT INTO paper_authors (pmid, author_id, author_position, affiliation)
                VALUES (?, 999999, ?, 'Test')
            """, test_row)
            conn.commit()
            assert False, "Should have failed UNIQUE constraint"
        except sqlite3.IntegrityError as e:
            print(f"  ✓ UNIQUE constraint enforced: {e}")
            conn.rollback()

    conn.close()
 
    print("\nStep 8: Cleanup...")
    test_db_path.unlink()
    print("  ✓ Test database deleted")
    print("===============================")
    print("\nDatabase Integration Test PASSED\n")
    print("===============================")


if __name__ == "__main__":
    test_database_integration()
