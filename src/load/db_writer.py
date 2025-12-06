"""Database writer for inserting parsed PubMed data into SQLite."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, Set
from utils.logger import get_logger

logger = get_logger(__name__)


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
            self._insert_keywords(cursor, pmid, paper.get('keywords', []))
            self._insert_mesh_terms(cursor, pmid, paper.get('mesh_terms', []))
            self._insert_publication_types(cursor, pmid, paper.get('publication_types', []))
            self._insert_grants(cursor, pmid, paper.get('grants', []))
            self._insert_chemicals(cursor, pmid, paper.get('chemicals', []))
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

    def _insert_keywords(self, cursor: sqlite3.Cursor, pmid: int, keywords: list) -> None:
        for keyword_data in keywords:
            keyword_id = self._get_or_create_keyword(cursor, keyword_data['keyword'])
            cursor.execute("""
                INSERT OR IGNORE INTO paper_keywords (pmid, keyword_id, is_major_topic)
                VALUES (?, ?, ?)
            """, (pmid, keyword_id, keyword_data.get('is_major_topic', False)))

    def _get_or_create_keyword(self, cursor: sqlite3.Cursor, keyword: str) -> int:
        cursor.execute("SELECT keyword_id FROM keywords WHERE keyword = ?", (keyword,))
        row = cursor.fetchone()
        if row:
            return row[0]
        cursor.execute("INSERT INTO keywords (keyword) VALUES (?)", (keyword,))
        return cursor.lastrowid

    def _insert_mesh_terms(self, cursor: sqlite3.Cursor, pmid: int, mesh_terms: list) -> None:
        for mesh_data in mesh_terms:
            mesh_id = self._get_or_create_mesh_term(
                cursor,
                mesh_data.get('descriptor_ui'),
                mesh_data['descriptor_name']
            )
            qualifiers_str = ', '.join(mesh_data.get('qualifiers', []) or [])
            cursor.execute("""
                INSERT OR IGNORE INTO paper_mesh_terms (pmid, mesh_id, is_major_topic, qualifier_names)
                VALUES (?, ?, ?, ?)
            """, (pmid, mesh_id, mesh_data.get('is_major_topic', False), qualifiers_str if qualifiers_str else None))

    def _get_or_create_mesh_term(self, cursor: sqlite3.Cursor, descriptor_ui: Optional[str], descriptor_name: str) -> int:
        if descriptor_ui:
            cursor.execute("SELECT mesh_id FROM mesh_terms WHERE descriptor_ui = ?", (descriptor_ui,))
            row = cursor.fetchone()
            if row:
                return row[0]
        cursor.execute("""
            INSERT INTO mesh_terms (descriptor_ui, descriptor_name) VALUES (?, ?)
        """, (descriptor_ui, descriptor_name))
        return cursor.lastrowid

    def _insert_publication_types(self, cursor: sqlite3.Cursor, pmid: int, pub_types: list) -> None:
        for pub_type_data in pub_types:
            pub_type_id = self._get_or_create_publication_type(
                cursor,
                pub_type_data.get('pub_type_ui'),
                pub_type_data['pub_type_name']
            )
            cursor.execute("""
                INSERT OR IGNORE INTO paper_publication_types (pmid, pub_type_id)
                VALUES (?, ?)
            """, (pmid, pub_type_id))

    def _get_or_create_publication_type(self, cursor: sqlite3.Cursor, pub_type_ui: Optional[str], pub_type_name: str) -> int:
        if pub_type_ui:
            cursor.execute("SELECT pub_type_id FROM publication_types WHERE pub_type_ui = ?", (pub_type_ui,))
            row = cursor.fetchone()
            if row:
                return row[0]
        cursor.execute("""
            INSERT INTO publication_types (pub_type_ui, pub_type_name) VALUES (?, ?)
        """, (pub_type_ui, pub_type_name))
        return cursor.lastrowid

    def _insert_grants(self, cursor: sqlite3.Cursor, pmid: int, grants: list) -> None:
        for grant_data in grants:
            grant_id = self._get_or_create_grant(
                cursor,
                grant_data['grant_number'],
                grant_data['agency'],
                grant_data.get('acronym'),
                grant_data.get('country')
            )
            cursor.execute("""
                INSERT OR IGNORE INTO paper_grants (pmid, grant_id)
                VALUES (?, ?)
            """, (pmid, grant_id))

    def _get_or_create_grant(self, cursor: sqlite3.Cursor, grant_number: str, agency: str, acronym: Optional[str], country: Optional[str]) -> int:
        cursor.execute("""
            SELECT grant_id FROM grants WHERE grant_number = ? AND agency = ?
        """, (grant_number, agency))
        row = cursor.fetchone()
        if row:
            return row[0]
        cursor.execute("""
            INSERT INTO grants (grant_number, grant_acronym, agency, country)
            VALUES (?, ?, ?, ?)
        """, (grant_number, acronym, agency, country))
        return cursor.lastrowid

    def _insert_chemicals(self, cursor: sqlite3.Cursor, pmid: int, chemicals: list) -> None:
        for chemical_data in chemicals:
            chemical_id = self._get_or_create_chemical(
                cursor,
                chemical_data.get('substance_ui'),
                chemical_data['substance_name'],
                chemical_data.get('registry_number')
            )
            cursor.execute("""
                INSERT OR IGNORE INTO paper_chemicals (pmid, chemical_id)
                VALUES (?, ?)
            """, (pmid, chemical_id))

    def _get_or_create_chemical(self, cursor: sqlite3.Cursor, substance_ui: Optional[str], substance_name: str, registry_number: Optional[str]) -> int:
        if substance_ui:
            cursor.execute("SELECT chemical_id FROM chemicals WHERE substance_ui = ?", (substance_ui,))
            row = cursor.fetchone()
            if row:
                return row[0]
        cursor.execute("""
            INSERT INTO chemicals (substance_ui, substance_name, registry_number)
            VALUES (?, ?, ?)
        """, (substance_ui, substance_name, registry_number))
        return cursor.lastrowid

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
