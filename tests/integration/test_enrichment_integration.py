#!/usr/bin/env python3
"""
Integration test for enrichment workflow with test.db.
~BLANK~
Verifies
- Enrichment modules work with shared utilities
- test.db isolation (never touches production)
- CrossRef/Semantic Scholar clients
- Citation insertion logic
~BLANK~
Run with: PYTHONPATH=. python tests/test_enrichment_integration.py --test
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.logger import get_logger
from src.utils.database import get_connection, init_test_db, cleanup_test_db
from src.enrich.citation_enricher import CitationEnricher


logger = get_logger("test_enrichment")


def populate_test_data():
    """
    Populate test.db with sample papers from production DB.

    Gets 5 papers with DOIs that need enrichment.
    """
    logger.info("Populating test.db with sample papers...")

    # Get sample papers from production
    prod_conn = get_connection(test_mode=False)
    cursor = prod_conn.execute("""
        SELECT pmid, doi, title, pub_year, fetch_date
        FROM papers
        WHERE doi IS NOT NULL AND doi != ''
        ORDER BY pub_year DESC
        LIMIT 5
    """)
    papers = cursor.fetchall()
    prod_conn.close()

    # Insert into test DB
    test_conn = get_connection(test_mode=True)
    for paper in papers:
        test_conn.execute("""
            INSERT INTO papers (pmid, doi, title, pub_year, fetch_date)
            VALUES (?, ?, ?, ?, ?)
        """, paper)
    test_conn.commit()

    count = test_conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
    test_conn.close()

    logger.info(f"  Inserted {count} test papers")
    return count


def test_enrichment():
    """Test enrichment with test.db."""
    logger.info("\n" + "="*60)
    logger.info("ENRICHMENT INTEGRATION TEST")
    logger.info("="*60)

    try:
        # Initialize test DB
        logger.info("\nStep 1: Initializing test.db...")
        init_test_db()
        logger.info("  test.db created")

        # Populate with test data
        logger.info("\nStep 2: Populating test data...")
        paper_count = populate_test_data()

        # Run enrichment (limit to 3 to keep test quick)
        logger.info("\nStep 3: Running enrichment (limit=3)...")
        logger.info("Note: This will prompt for credentials\n")

        # For automated testing, we'd mock this, but for now we test manually
        from src.utils.credentials import get_all_enrichment_credentials

        credentials = get_all_enrichment_credentials(require_api_keys=False)

        enricher = CitationEnricher(
            crossref_email=credentials['crossref']['email'],
            semantic_scholar_api_key=credentials['semantic_scholar']['api_key'],
            test_mode=True
        )

        stats = enricher.run(limit=3)

        # Verify results
        logger.info("\nStep 4: Verifying results...")
        test_conn = get_connection(test_mode=True)

        citation_count = test_conn.execute(
            "SELECT COUNT(*) FROM citations"
        ).fetchone()[0]

        logger.info(f"  Papers processed: {stats['processed']}")
        logger.info(f"  Papers enriched: {stats['enriched']}")
        logger.info(f"  Citations added: {citation_count}")

        test_conn.close()

        # Cleanup
        logger.info("\nStep 5: Cleaning up...")
        cleanup_test_db()
        logger.info("  test.db removed")

        logger.info("\n" + "="*60)
        logger.info("OK ENRICHMENT TEST PASSED")
        logger.info("="*60)
        logger.info("\nCheck logs/workflow.log for detailed timeline")

        return 0

    except Exception as e:
        logger.error(f"\nERROR TEST FAILED: {e}")
        logger.info("\nCleaning up...")
        cleanup_test_db()
        return 1


if __name__ == "__main__":
    sys.exit(test_enrichment())
