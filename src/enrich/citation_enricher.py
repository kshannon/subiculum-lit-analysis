"""
Citation enrichment orchestrator.

Coordinates fetching citations from external APIs and storing in database.
"""

from typing import Dict, List, Optional
from datetime import datetime
from src.utils.logger import get_logger
from src.utils.database import get_connection
from .crossref_client import CrossRefClient
from .semantic_scholar_client import SemanticScholarClient


logger = get_logger(__name__)


class CitationEnricher:
    """Orchestrates citation enrichment from multiple sources."""

    def __init__(
        self,
        crossref_email: str,
        semantic_scholar_api_key: Optional[str] = None,
        test_mode: bool = False
    ):
        """
        Initialize enricher with API clients.

        Args:
            crossref_email: Email for CrossRef polite pool
            semantic_scholar_api_key: Optional S2 API key
            test_mode: If True, uses test.db instead of production
        """
        self.test_mode = test_mode
        self.crossref = CrossRefClient(crossref_email)
        self.semantic_scholar = SemanticScholarClient(semantic_scholar_api_key)

        logger.info(f"Citation enricher initialized (test_mode={test_mode})")

    def get_papers_without_citations(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Get papers that have DOIs but no citations in database.

        Args:
            limit: Optional limit on number of papers

        Returns:
            List of dicts with paper info: [{'pmid': ..., 'doi': ..., 'title': ...}]
        """
        conn = get_connection(test_mode=self.test_mode)
        cursor = conn.cursor()

        query = """
        SELECT p.pmid, p.doi, p.title
        FROM papers p
        LEFT JOIN citations c ON p.pmid = c.citing_pmid
        WHERE p.doi IS NOT NULL
          AND p.doi != ''
          AND c.citing_pmid IS NULL
        GROUP BY p.pmid
        ORDER BY p.pub_year DESC
        """

        if limit:
            query += f" LIMIT {limit}"

        cursor.execute(query)
        results = [
            {'pmid': row[0], 'doi': row[1], 'title': row[2]}
            for row in cursor.fetchall()
        ]
        conn.close()

        return results

    def doi_to_pmid(self, doi: str) -> Optional[int]:
        """
        Look up PMID for a DOI in database.

        Args:
            doi: DOI to look up

        Returns:
            PMID if found, None otherwise
        """
        conn = get_connection(test_mode=self.test_mode)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT pmid FROM papers WHERE LOWER(doi) = LOWER(?)",
            (doi,)
        )
        result = cursor.fetchone()
        conn.close()

        return result[0] if result else None

    def insert_citations(self, citing_pmid: int, cited_dois: List[str], source: str) -> int:
        """
        Insert citations into database.

        Args:
            citing_pmid: PMID of paper doing the citing
            cited_dois: List of DOIs being cited
            source: 'crossref' or 'semantic_scholar'

        Returns:
            Number of citations inserted
        """
        if not cited_dois:
            return 0

        conn = get_connection(test_mode=self.test_mode)
        cursor = conn.cursor()
        inserted = 0

        for cited_doi in cited_dois:
            cited_pmid = self.doi_to_pmid(cited_doi)

            if cited_pmid:
                try:
                    cursor.execute("""
                        INSERT OR IGNORE INTO citations (citing_pmid, cited_pmid)
                        VALUES (?, ?)
                    """, (citing_pmid, cited_pmid))

                    if cursor.rowcount > 0:
                        inserted += 1

                except Exception as e:
                    logger.debug(f"Citation already exists: {citing_pmid} -> {cited_pmid}")

        conn.commit()
        conn.close()

        return inserted

    def enrich_paper(self, paper: Dict, stats: Dict) -> None:
        """
        Enrich a single paper with citation data.

        Tries CrossRef first, falls back to Semantic Scholar.
        Updates stats dict in place.

        Args:
            paper: Dict with 'pmid', 'doi', 'title'
            stats: Statistics dict to update
        """
        pmid = paper['pmid']
        doi = paper['doi']
        title = paper['title']

        logger.info(f"[{stats['processed'] + 1}/{stats['total']}] PMID {pmid}")
        logger.info(f"  DOI: {doi}")
        logger.info(f"  Title: {title[:70]}...")

        # Try CrossRef first
        logger.info("  Trying CrossRef...")
        cited_dois = self.crossref.fetch_references(doi)

        if cited_dois:
            logger.info(f"  Found {len(cited_dois)} references")
            inserted = self.insert_citations(pmid, cited_dois, 'crossref')
            logger.info(f"  Saved {inserted} citations (source: crossref)")

            stats['processed'] += 1
            stats['enriched'] += 1
            stats['crossref_success'] += 1
            stats['total_citations_added'] += inserted
            return

        logger.info("  Not found in CrossRef")

        # Try Semantic Scholar as backup
        logger.info("  Trying Semantic Scholar...")
        cited_dois = self.semantic_scholar.fetch_references(doi)

        if cited_dois:
            logger.info(f"  Found {len(cited_dois)} references")
            inserted = self.insert_citations(pmid, cited_dois, 'semantic_scholar')
            logger.info(f"  Saved {inserted} citations (source: semantic_scholar)")

            stats['processed'] += 1
            stats['enriched'] += 1
            stats['s2_success'] += 1
            stats['total_citations_added'] += inserted
            return

        logger.info("  Not found in Semantic Scholar")
        logger.info("  No references found in any API")
        stats['processed'] += 1
        stats['not_found'] += 1

    def run(self, limit: Optional[int] = None) -> Dict:
        """
        Run enrichment pipeline.

        Args:
            limit: Optional limit on number of papers to process

        Returns:
            Statistics dict with results
        """
        logger.info("="*80)
        logger.info("Starting citation enrichment")
        logger.info("="*80)

        papers = self.get_papers_without_citations(limit=limit)

        if not papers:
            logger.info("No papers need enrichment")
            return {'total': 0, 'processed': 0}

        logger.info(f"Found {len(papers)} papers without citations")

        if limit:
            logger.info(f"LIMIT set to {limit}")

        stats = {
            'total': len(papers),
            'processed': 0,
            'enriched': 0,
            'not_found': 0,
            'crossref_success': 0,
            's2_success': 0,
            'total_citations_added': 0
        }

        start_time = datetime.now()

        for paper in papers:
            try:
                self.enrich_paper(paper, stats)
            except KeyboardInterrupt:
                logger.info("Interrupted by user")
                break
            except Exception as e:
                logger.error(f"Error processing PMID {paper['pmid']}: {e}")
                stats['processed'] += 1
                continue

        elapsed = (datetime.now() - start_time).total_seconds()

        logger.info("="*80)
        logger.info("ENRICHMENT SUMMARY")
        logger.info("="*80)
        logger.info(f"Papers processed: {stats['processed']}/{stats['total']}")
        logger.info(f"Successfully enriched: {stats['enriched']} ({100*stats['enriched']/stats['total']:.1f}%)")
        logger.info(f"Not found: {stats['not_found']}")
        logger.info(f"API breakdown:")
        logger.info(f"  CrossRef: {stats['crossref_success']} papers")
        logger.info(f"  Semantic Scholar: {stats['s2_success']} papers")
        logger.info(f"Total citations added: {stats['total_citations_added']}")
        logger.info(f"Runtime: {elapsed:.1f}s ({elapsed/60:.1f} min)")
        logger.info("="*80)

        return stats
