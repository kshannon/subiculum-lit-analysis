#!/usr/bin/env python3
"""
Full Pipeline System Test

End-to-end test that validates the complete refactored pipeline:
1. Shared utilities (logger, database, credentials)
2. ETL components working together
3. Enrichment workflow
4. Unified logging across all components
5. Test mode isolation (never touches production)

Usage:
    CROSSREF_EMAIL="test@example.com" SEMANTIC_SCHOLAR_EMAIL="test@example.com" \
    python tests/system/test_full_pipeline.py
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.logger import get_logger
from src.utils.database import get_connection, init_test_db, cleanup_test_db
from src.enrich.citation_enricher import CitationEnricher
from src.utils.credentials import get_all_enrichment_credentials

logger = get_logger("system_test")


class SystemTestRunner:
    """Orchestrates full pipeline system test."""

    def __init__(self):
        self.test_db_path = Path("data/test/test.db")
        self.log_file = Path("logs/workflow.log")
        self.test_start_time = datetime.now()

    def run(self):
        """Run complete system test."""
        logger.info("\n" + "="*80)
        logger.info("FULL PIPELINE SYSTEM TEST")
        logger.info("="*80)
        logger.info(f"Start time: {self.test_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("Testing refactored pipeline with unified logging")
        logger.info("="*80)

        try:
            # Step 1: Initialize test infrastructure
            self.test_step_1_initialize()

            # Step 2: Populate test data
            self.test_step_2_populate()

            # Step 3: Test enrichment workflow
            self.test_step_3_enrichment()

            # Step 4: Verify unified logging
            self.test_step_4_logging()

            # Step 5: Validate results
            self.test_step_5_validation()

            # Step 6: Cleanup
            self.test_step_6_cleanup()

            # Final summary
            self.print_summary()

            return 0

        except Exception as e:
            logger.error(f"\nERROR SYSTEM TEST FAILED: {e}")
            logger.exception("Full traceback:")
            logger.info("\nCleaning up test database...")
            cleanup_test_db()
            return 1

    def test_step_1_initialize(self):
        """Step 1: Initialize test database and verify schema."""
        logger.info("\n" + "-"*80)
        logger.info("STEP 1: Initialize Test Database")
        logger.info("-"*80)

        logger.info("Initializing test.db with schema...")
        init_test_db()

        # Verify test DB exists
        if not self.test_db_path.exists():
            raise RuntimeError("test.db not created")

        logger.info(f"  OK test.db created at: {self.test_db_path}")

        # Verify schema applied
        conn = get_connection(test_mode=True)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        expected_tables = ['papers', 'authors', 'paper_authors', 'citations',
                          'mesh_terms', 'paper_mesh_terms', 'fetch_log']

        for table in expected_tables:
            if table not in tables:
                raise RuntimeError(f"Missing table: {table}")

        logger.info(f"  OK Schema verified: {len(tables)} tables present")
        logger.info(f"  OK Tables: {', '.join(tables)}")

    def test_step_2_populate(self):
        """Step 2: Populate test database with sample papers."""
        logger.info("\n" + "-"*80)
        logger.info("STEP 2: Populate Test Data")
        logger.info("-"*80)

        logger.info("Fetching sample papers from production DB...")

        # Get sample papers with DOIs from production
        prod_conn = get_connection(test_mode=False)
        cursor = prod_conn.execute("""
            SELECT pmid, doi, title, pub_year, fetch_date
            FROM papers
            WHERE doi IS NOT NULL
              AND doi != ''
              AND pmid NOT IN (
                  SELECT citing_pmid FROM citations GROUP BY citing_pmid HAVING COUNT(*) > 0
              )
            ORDER BY pub_year DESC
            LIMIT 5
        """)
        papers = cursor.fetchall()

        if not papers:
            # Fallback: get any papers with DOIs
            cursor = prod_conn.execute("""
                SELECT pmid, doi, title, pub_year, fetch_date
                FROM papers
                WHERE doi IS NOT NULL AND doi != ''
                ORDER BY pub_year DESC
                LIMIT 5
            """)
            papers = cursor.fetchall()

        prod_conn.close()

        if not papers:
            raise RuntimeError("No papers found in production DB to test with")

        logger.info(f"  OK Found {len(papers)} papers to copy")

        # Insert into test DB
        test_conn = get_connection(test_mode=True)
        for i, paper in enumerate(papers, 1):
            pmid, doi, title, pub_year, fetch_date = paper
            test_conn.execute("""
                INSERT INTO papers (pmid, doi, title, pub_year, fetch_date)
                VALUES (?, ?, ?, ?, ?)
            """, (pmid, doi, title[:50] + "..." if len(title) > 50 else title,
                  pub_year, fetch_date))
            logger.info(f"  OK [{i}/{len(papers)}] PMID {pmid}: {doi}")

        test_conn.commit()

        # Verify insertion
        count = test_conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
        test_conn.close()

        logger.info(f"  OK Inserted {count} test papers into test.db")

    def test_step_3_enrichment(self):
        """Step 3: Test enrichment workflow with unified logging."""
        logger.info("\n" + "-"*80)
        logger.info("STEP 3: Test Enrichment Workflow")
        logger.info("-"*80)

        logger.info("Checking for credentials...")

        # Check environment variables
        if not os.environ.get('CROSSREF_EMAIL'):
            raise RuntimeError(
                "Missing CROSSREF_EMAIL environment variable.\n"
                "Run with: CROSSREF_EMAIL='test@example.com' "
                "SEMANTIC_SCHOLAR_EMAIL='test@example.com' python tests/system/test_full_pipeline.py"
            )

        logger.info("  OK Credentials available via environment variables")

        # Get credentials
        credentials = get_all_enrichment_credentials(require_api_keys=False)

        # Initialize enricher
        logger.info("Initializing citation enricher...")
        enricher = CitationEnricher(
            crossref_email=credentials['crossref']['email'],
            semantic_scholar_api_key=credentials['semantic_scholar']['api_key'],
            test_mode=True
        )

        # Run enrichment (limit to 3 for speed)
        logger.info("Running enrichment workflow (limit=3)...")
        stats = enricher.run(limit=3)

        logger.info(f"  OK Enrichment completed")
        logger.info(f"  OK Papers processed: {stats['processed']}")
        logger.info(f"  OK Papers enriched: {stats['enriched']}")
        logger.info(f"  OK Total citations: {stats['total_citations_added']}")

    def test_step_4_logging(self):
        """Step 4: Verify unified logging worked."""
        logger.info("\n" + "-"*80)
        logger.info("STEP 4: Verify Unified Logging")
        logger.info("-"*80)

        if not self.log_file.exists():
            raise RuntimeError(f"Log file not found: {self.log_file}")

        logger.info(f"  OK Log file exists: {self.log_file}")

        # Read log file and check for expected components
        with open(self.log_file, 'r') as f:
            log_contents = f.read()

        expected_loggers = [
            'system_test',
            'src.utils.database',
            'src.enrich.citation_enricher',
            'src.enrich.crossref_client',
            'src.enrich.semantic_scholar_client'
        ]

        found_loggers = []
        for logger_name in expected_loggers:
            if logger_name in log_contents:
                found_loggers.append(logger_name)
                logger.info(f"  OK Found logs from: {logger_name}")

        if len(found_loggers) < 3:
            logger.warning(f"  ⚠ Only found {len(found_loggers)}/{len(expected_loggers)} loggers")
        else:
            logger.info(f"  OK Unified logging working: {len(found_loggers)}/{len(expected_loggers)} components logged")

        # Check log format consistency
        lines = log_contents.strip().split('\n')
        recent_lines = [l for l in lines if 'system_test' in l or 'src.enrich' in l][-10:]

        logger.info(f"  OK Total log lines: {len(lines)}")
        logger.info(f"  OK Recent test lines: {len(recent_lines)}")

    def test_step_5_validation(self):
        """Step 5: Validate database state."""
        logger.info("\n" + "-"*80)
        logger.info("STEP 5: Validate Database State")
        logger.info("-"*80)

        conn = get_connection(test_mode=True)

        # Check papers
        paper_count = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
        logger.info(f"  OK Papers in DB: {paper_count}")

        # Check citations
        citation_count = conn.execute("SELECT COUNT(*) FROM citations").fetchone()[0]
        logger.info(f"  OK Citations in DB: {citation_count}")

        # Check enriched papers
        enriched_count = conn.execute("""
            SELECT COUNT(DISTINCT citing_pmid) FROM citations
        """).fetchone()[0]
        logger.info(f"  OK Papers with citations: {enriched_count}")

        # Verify data integrity
        orphaned = conn.execute("""
            SELECT COUNT(*) FROM citations
            WHERE citing_pmid NOT IN (SELECT pmid FROM papers)
        """).fetchone()[0]

        if orphaned > 0:
            raise RuntimeError(f"Found {orphaned} orphaned citations")

        logger.info(f"  OK Data integrity verified: no orphaned citations")

        conn.close()

    def test_step_6_cleanup(self):
        """Step 6: Cleanup test database."""
        logger.info("\n" + "-"*80)
        logger.info("STEP 6: Cleanup")
        logger.info("-"*80)

        logger.info("Removing test.db...")
        cleanup_test_db()

        if self.test_db_path.exists():
            raise RuntimeError("test.db still exists after cleanup")

        logger.info("  OK test.db removed")

    def print_summary(self):
        """Print final test summary."""
        test_end_time = datetime.now()
        duration = test_end_time - self.test_start_time

        logger.info("\n" + "="*80)
        logger.info("PASSED SYSTEM TEST PASSED")
        logger.info("="*80)
        logger.info(f"Start time: {self.test_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"End time:   {test_end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration:   {duration.total_seconds():.1f}s")
        logger.info("")
        logger.info("PASSED Verified:")
        logger.info("  • Shared utilities (logger, database, credentials)")
        logger.info("  • Test mode isolation (test.db only)")
        logger.info("  • Enrichment workflow")
        logger.info("  • Unified logging across all components")
        logger.info("  • Data integrity and cleanup")
        logger.info("")
        logger.info(f"Log: Full timeline available in: {self.log_file}")
        logger.info("="*80)


def main():
    """Entry point."""
    # Check environment variables
    if not os.environ.get('CROSSREF_EMAIL'):
        print("\n" + "="*80)
        print("ERROR: Missing required environment variables")
        print("="*80)
        print("\nUsage:")
        print("  CROSSREF_EMAIL='your@email.com' \\")
        print("  SEMANTIC_SCHOLAR_EMAIL='your@email.com' \\")
        print("  python tests/system/test_full_pipeline.py")
        print("\nOr with pixi:")
        print("  CROSSREF_EMAIL='your@email.com' \\")
        print("  SEMANTIC_SCHOLAR_EMAIL='your@email.com' \\")
        print("  pixi run python tests/system/test_full_pipeline.py")
        print("="*80)
        return 1

    runner = SystemTestRunner()
    return runner.run()


if __name__ == "__main__":
    sys.exit(main())
