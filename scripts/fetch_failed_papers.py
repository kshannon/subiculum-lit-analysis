#!/usr/bin/env python3
"""
Fetch Failed Papers

Reads PMIDs from logs/write_failure.log and attempts to fetch them individually
with enhanced error handling and citation deduplication.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import ConfigManager
from extract.api_client import PubMedAPIClient
from transform.xml_parser import parse_xml_batch
from load.db_writer import DatabaseWriter
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def deduplicate_citations(citations):
    """Remove duplicate citations by (cited_pmid, cited_doi) tuple."""
    seen = set()
    unique = []

    for citation in citations:
        key = (citation.get('cited_pmid'), citation.get('cited_doi'))
        if key not in seen:
            seen.add(key)
            unique.append(citation)

    return unique


def main():
    failure_log = Path("logs/write_failure.log")

    if not failure_log.exists():
        logger.info("No failure log found. All papers inserted successfully!")
        return

    # Read failed PMIDs
    failed_pmids = set()
    with open(failure_log, 'r') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 2:
                try:
                    pmid = int(parts[1])
                    failed_pmids.add(pmid)
                except ValueError:
                    continue

    logger.info(f"Found {len(failed_pmids)} unique failed PMIDs")

    if not failed_pmids:
        logger.info("No PMIDs to retry.")
        return

    # Initialize components
    config = ConfigManager("settings.yaml")
    api_client = PubMedAPIClient(
        email=config.pubmed_email,
        api_key=config.pubmed_api_key,
        tool=config.pubmed_tool,
        rate_limit=config.rate_limit
    )

    db_writer = DatabaseWriter("data/subiculum_literature.db")
    db_writer.connect()

    # Fetch each PMID individually
    success_count = 0
    still_failing = []

    for i, pmid in enumerate(sorted(failed_pmids), 1):
        logger.info(f"[{i}/{len(failed_pmids)}] Fetching PMID {pmid}...")

        try:
            xml_data = api_client.fetch_by_pmids([pmid])
            papers = parse_xml_batch(xml_data)

            if not papers:
                logger.warning(f"  No paper parsed for PMID {pmid}")
                still_failing.append(pmid)
                continue

            paper = papers[0]

            # Deduplicate citations
            if 'citations' in paper:
                original_count = len(paper['citations'])
                paper['citations'] = deduplicate_citations(paper['citations'])
                deduped_count = len(paper['citations'])

                if original_count != deduped_count:
                    logger.info(f"  Deduplicated citations: {original_count} → {deduped_count}")

            if db_writer.insert_paper(paper):
                logger.info(f"  ✓ Successfully inserted PMID {pmid}")
                success_count += 1
            else:
                logger.warning(f"  ✗ Still failing: PMID {pmid}")
                still_failing.append(pmid)

        except Exception as e:
            logger.error(f"  ✗ Error fetching PMID {pmid}: {e}")
            still_failing.append(pmid)

    db_writer.close()

    logger.info("\n=== Retry Complete ===")
    logger.info(f"Successfully inserted: {success_count}/{len(failed_pmids)}")
    logger.info(f"Still failing: {len(still_failing)}")

    if still_failing:
        logger.info(f"Remaining failed PMIDs: {sorted(still_failing)}")


if __name__ == "__main__":
    main()
