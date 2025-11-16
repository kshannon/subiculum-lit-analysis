#!/usr/bin/env python3
"""
ETL Pipeline Orchestrator

Fetches PubMed data, parses XML, and loads into database.
Handles batching, rate limiting, idempotency, and error recovery.
"""

import logging
import sys
from pathlib import Path
from typing import Set

from config import ConfigManager
from extract.api_client import PubMedAPIClient
from transform.xml_parser import parse_xml_batch
from load.db_writer import DatabaseWriter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/pipeline.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class Pipeline:
    """
    Orchestrates the ETL pipeline for PubMed literature data.

    Handles:
    - Idempotency (skips already-fetched papers)
    - Batching (100 papers per API call)
    - Per-paper transactions (continues on individual failures)
    - Progress logging
    """

    def __init__(self, config_path: str = "settings.yaml", db_path: str = "data/subiculum_literature.db"):
        self.config = ConfigManager(config_path)
        self.db_path = db_path
        self.api_client: PubMedAPIClient = None
        self.db_writer: DatabaseWriter = None
        self.batch_size = 100

    def run(self) -> None:
        logger.info("Starting ETL pipeline")
        logger.info(f"Search query: {self.config.search_query}")

        Path("logs").mkdir(exist_ok=True)

        self.api_client = PubMedAPIClient(
            email=self.config.pubmed_email,
            api_key=self.config.pubmed_api_key,
            tool=self.config.pubmed_tool,
            rate_limit=self.config.rate_limit
        )

        search_query = self.config.search_query
        if 'MeSH' in search_query and 'Title/Abstract' in search_query:
            search_source = 'title_abstract_and_mesh'
        elif 'MeSH' in search_query:
            search_source = 'mesh'
        else:
            search_source = 'title_abstract'

        self.db_writer = DatabaseWriter(
            self.db_path,
            search_source=search_source,
            search_query=search_query
        )
        self.db_writer.connect()

        try:
            # Get already-fetched PMIDs for idempotency
            fetched_pmids = self.db_writer.get_fetched_pmids()
            logger.info(f"Already fetched: {len(fetched_pmids)} papers")

            # Run ESearch to get all PMIDs
            logger.info("Running ESearch...")
            search_result = self.api_client.search(
                query=self.config.search_query,
                use_history=True,
                retmax=0  # Just get count and WebEnv
            )

            total_papers = search_result.count
            web_env = search_result.webenv
            query_key = search_result.query_key

            logger.info(f"Total papers found: {total_papers}")
            logger.info(f"WebEnv: {web_env[:20]}...")
            logger.info(f"Query key: {query_key}")

            remaining = total_papers - len(fetched_pmids)
            logger.info(f"Papers remaining to fetch: {remaining}")

            if remaining == 0:
                logger.info("All papers already fetched. Pipeline complete.")
                return

            # Fetch and process in batches
            total_inserted = 0
            total_failed = 0

            for start in range(0, total_papers, self.batch_size):
                batch_num = (start // self.batch_size) + 1
                total_batches = (total_papers + self.batch_size - 1) // self.batch_size

                logger.info(f"\n--- Batch {batch_num}/{total_batches} (papers {start+1}-{min(start+self.batch_size, total_papers)}) ---")

                try:
                    xml_data = self.api_client.fetch_batch(
                        webenv=web_env,
                        query_key=query_key,
                        retstart=start,
                        retmax=self.batch_size
                    )
                except Exception as e:
                    logger.error(f"Failed to fetch batch {batch_num}: {e}")
                    continue

                try:
                    papers = parse_xml_batch(xml_data)
                    logger.info(f"Parsed {len(papers)} papers from XML")
                except Exception as e:
                    logger.error(f"Failed to parse batch {batch_num}: {e}")
                    continue

                batch_inserted = 0
                batch_failed = 0
                batch_skipped = 0

                for paper in papers:
                    pmid = paper['pmid']

                    # Skip if already fetched
                    if pmid in fetched_pmids:
                        batch_skipped += 1
                        continue

                    # Insert paper
                    if self.db_writer.insert_paper(paper):
                        batch_inserted += 1
                        fetched_pmids.add(pmid)  # Update local cache
                    else:
                        batch_failed += 1

                logger.info(f"Batch results: {batch_inserted} inserted, {batch_failed} failed, {batch_skipped} skipped")
                total_inserted += batch_inserted
                total_failed += batch_failed

            logger.info("\n=== Pipeline Complete ===")
            logger.info(f"Total papers inserted: {total_inserted}")
            logger.info(f"Total papers failed: {total_failed}")
            logger.info(f"Total papers in database: {len(fetched_pmids)}")

            if total_failed > 0:
                logger.info(f"Failed PMIDs logged to: logs/write_failure.log")

        finally:
            self.db_writer.close()
            logger.info("Database connection closed")


if __name__ == "__main__":
    pipeline = Pipeline()
    pipeline.run()
