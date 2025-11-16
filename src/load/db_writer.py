"""Database writer for inserting parsed PubMed data into SQLite."""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, Set

logger = logging.getLogger(__name__)


class DatabaseWriter:
    """
    Handles transactional insertion of papers, authors, and citations.

    Transaction strategy: One transaction per paper (not per batch).
    If insert fails, PMID is logged to logs/write_failure.log.
    """

    def __init__(self, db_path: str, search_source: str = 'title_abstract', search_query: str = 'subiculum[Title/Abstract]'):
        self.db_path = Path(db_path)
        self.conn: Optional[sqlite3.Connection] = None
        self.failure_log_path = Path("logs/write_failure.log")
        self.failure_log_path.parent.mkdir(exist_ok=True)
        self.search_source = search_source
        self.search_query = search_query

    def connect(self) -> None:
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")

        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.execute("PRAGMA foreign_keys = ON")
        logger.info(f"Connected to database: {self.db_path}")

    def insert_paper(self, paper: dict) -> bool:
        """
        Insert single paper with authors and citations in one transaction.

        Returns True if successful, False otherwise.
        Logs failures to logs/write_failure.log.
        """
        if not self.conn:
            raise RuntimeError("Not connected to database. Call connect() first.")

        pmid = paper['pmid']
        cursor = self.conn.cursor()

        try:
            cursor.execute("BEGIN TRANSACTION")
            self._insert_paper_record(cursor, paper)
            self._insert_authors(cursor, pmid, paper.get('authors', []))
            self._insert_citations(cursor, pmid, paper.get('citations', []))
            self._insert_open_access(cursor, pmid, paper.get('open_access', {}))
            self._update_fetch_log(cursor, pmid, success=True)
            self._insert_search_source(cursor, pmid)

            self.conn.commit()
            logger.debug(f"Inserted paper PMID {pmid}")
            return True

        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to insert PMID {pmid}: {e}")
            self._log_failure(pmid, str(e))
            return False

    def _insert_paper_record(self, cursor: sqlite3.Cursor, paper: dict) -> None:
        cursor.execute("""
            INSERT INTO papers (
                pmid, doi, pmc_id, title, abstract, language,
                journal_name, journal_issn, journal_iso_abbrev,
                pub_year, pub_month, pub_day,
                volume, issue, pages, publication_status,
                fetch_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            paper['pmid'],
            paper.get('doi'),
            paper.get('pmc_id'),
            paper['title'],
            paper.get('abstract'),
            paper.get('language'),
            paper.get('journal_name'),
            paper.get('journal_issn'),
            paper.get('journal_iso_abbrev'),
            paper.get('pub_year'),
            paper.get('pub_month'),
            paper.get('pub_day'),
            paper.get('volume'),
            paper.get('issue'),
            paper.get('pages'),
            paper.get('publication_status'),
            datetime.now().isoformat()
        ))

    def _insert_authors(self, cursor: sqlite3.Cursor, pmid: int, authors: list) -> None:
        for author in authors:
            # Get or create author_id
            author_id = self._get_or_create_author(
                cursor,
                author['last_name'],
                author.get('fore_name'),
                author.get('initials'),
                author.get('orcid')
            )

            # Link author to paper
            cursor.execute("""
                INSERT INTO paper_authors (pmid, author_id, author_position, affiliation)
                VALUES (?, ?, ?, ?)
            """, (pmid, author_id, author['position'], author.get('affiliation')))

    def _get_or_create_author(
        self,
        cursor: sqlite3.Cursor,
        last_name: str,
        fore_name: Optional[str],
        initials: Optional[str],
        orcid: Optional[str]
    ) -> int:
        """Get existing author_id or create new author."""
        # Try to find existing author
        cursor.execute("""
            SELECT author_id FROM authors
            WHERE last_name = ? AND fore_name IS ? AND orcid IS ?
        """, (last_name, fore_name, orcid))

        row = cursor.fetchone()
        if row:
            return row[0]

        # Create new author
        cursor.execute("""
            INSERT INTO authors (last_name, fore_name, initials, orcid)
            VALUES (?, ?, ?, ?)
        """, (last_name, fore_name, initials, orcid))

        return cursor.lastrowid

    def _insert_citations(self, cursor: sqlite3.Cursor, pmid: int, citations: list) -> None:
        for citation in citations:
            cursor.execute("""
                INSERT INTO citations (citing_pmid, cited_pmid, cited_doi, citation_text)
                VALUES (?, ?, ?, ?)
            """, (pmid, citation.get('cited_pmid'), citation.get('cited_doi'), citation.get('citation_text')))

    def _update_fetch_log(self, cursor: sqlite3.Cursor, pmid: int, success: bool) -> None:
        cursor.execute("""
            INSERT INTO fetch_log (pmid, fetch_attempt_date, fetch_success, retry_count)
            VALUES (?, ?, ?, 0)
        """, (pmid, datetime.now().isoformat(), success))

    def _insert_search_source(self, cursor: sqlite3.Cursor, pmid: int) -> None:
        cursor.execute("""
            INSERT OR IGNORE INTO paper_search_sources (pmid, search_type, search_query, found_date)
            VALUES (?, ?, ?, ?)
        """, (pmid, self.search_source, self.search_query, datetime.now().isoformat()))

    def _insert_open_access(self, cursor: sqlite3.Cursor, pmid: int, open_access: dict) -> None:
        if not open_access:
            return

        cursor.execute("""
            INSERT OR IGNORE INTO paper_open_access (pmid, pmc_id, is_open_access, pmc_url, pdf_url, license)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            pmid,
            open_access.get('pmc_id'),
            open_access.get('is_open_access', False),
            open_access.get('pmc_url'),
            open_access.get('pdf_url'),
            open_access.get('license')
        ))

    def _log_failure(self, pmid: int, error_message: str) -> None:
        with open(self.failure_log_path, 'a') as f:
            f.write(f"{datetime.now().isoformat()}\t{pmid}\t{error_message}\n")

    def get_fetched_pmids(self) -> Set[int]:
        """
        Get set of PMIDs already successfully processed.

        Returns set of PMIDs from fetch_log where fetch_success = TRUE.
        """
        if not self.conn:
            raise RuntimeError("Not connected to database. Call connect() first.")

        cursor = self.conn.cursor()
        cursor.execute("SELECT pmid FROM fetch_log WHERE fetch_success = 1")
        return {row[0] for row in cursor.fetchall()}

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("Database connection closed")

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def __repr__(self) -> str:
        return f"DatabaseWriter(db_path={self.db_path})"
