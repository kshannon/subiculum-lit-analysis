#!/usr/bin/env python3
"""
Re-enrich all papers with keywords, MeSH terms, publication types, grants, and chemicals.

Fetches fresh XML from PubMed for all papers and extracts metadata.
Safe to re-run - uses INSERT OR IGNORE to avoid duplicates.
"""

import sys
import os
from pathlib import Path
import time

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from extract.pubmed_client import PubMedAPIClient
from transform.xml_parser import parse_xml_batch
from utils.database import get_connection
from utils.logger import get_logger
from utils.credentials import get_api_credentials

logger = get_logger("metadata_enrichment")

BATCH_SIZE = 100  # Reduced to avoid URL length limits (414 errors)


def get_all_pmids():
    """Get all PMIDs from database."""
    conn = get_connection()
    cursor = conn.execute("SELECT pmid FROM papers ORDER BY pmid")
    pmids = [row[0] for row in cursor.fetchall()]
    conn.close()
    return pmids


def insert_metadata_only(conn, paper):
    """Insert only metadata (keywords, mesh, grants, pub_types, chemicals)."""
    pmid = paper['pmid']
    cursor = conn.cursor()

    try:
        cursor.execute("BEGIN TRANSACTION")

        # Keywords
        for keyword_data in paper.get('keywords', []):
            cursor.execute("""
                INSERT OR IGNORE INTO keywords (keyword) VALUES (?)
            """, (keyword_data['keyword'],))
            cursor.execute("SELECT keyword_id FROM keywords WHERE keyword = ?", (keyword_data['keyword'],))
            keyword_id = cursor.fetchone()[0]
            cursor.execute("""
                INSERT OR IGNORE INTO paper_keywords (pmid, keyword_id, is_major_topic)
                VALUES (?, ?, ?)
            """, (pmid, keyword_id, keyword_data.get('is_major_topic', False)))

        # MeSH terms
        for mesh_data in paper.get('mesh_terms', []):
            cursor.execute("""
                INSERT OR IGNORE INTO mesh_terms (descriptor_ui, descriptor_name)
                VALUES (?, ?)
            """, (mesh_data.get('descriptor_ui'), mesh_data['descriptor_name']))
            cursor.execute("""
                SELECT mesh_id FROM mesh_terms
                WHERE descriptor_ui IS ? AND descriptor_name = ?
            """, (mesh_data.get('descriptor_ui'), mesh_data['descriptor_name']))
            mesh_id = cursor.fetchone()[0]
            qualifiers_str = ', '.join(mesh_data.get('qualifiers', []) or [])
            cursor.execute("""
                INSERT OR IGNORE INTO paper_mesh_terms (pmid, mesh_id, is_major_topic, qualifier_names)
                VALUES (?, ?, ?, ?)
            """, (pmid, mesh_id, mesh_data.get('is_major_topic', False), qualifiers_str if qualifiers_str else None))

        # Publication types
        for pub_type_data in paper.get('publication_types', []):
            cursor.execute("""
                INSERT OR IGNORE INTO publication_types (pub_type_ui, pub_type_name)
                VALUES (?, ?)
            """, (pub_type_data.get('pub_type_ui'), pub_type_data['pub_type_name']))
            cursor.execute("""
                SELECT pub_type_id FROM publication_types WHERE pub_type_ui IS ? AND pub_type_name = ?
            """, (pub_type_data.get('pub_type_ui'), pub_type_data['pub_type_name']))
            pub_type_id = cursor.fetchone()[0]
            cursor.execute("""
                INSERT OR IGNORE INTO paper_publication_types (pmid, pub_type_id)
                VALUES (?, ?)
            """, (pmid, pub_type_id))

        # Grants
        for grant_data in paper.get('grants', []):
            cursor.execute("""
                INSERT OR IGNORE INTO grants (grant_number, grant_acronym, agency, country)
                VALUES (?, ?, ?, ?)
            """, (grant_data['grant_number'], grant_data.get('acronym'), grant_data['agency'], grant_data.get('country')))
            cursor.execute("""
                SELECT grant_id FROM grants WHERE grant_number = ? AND agency = ?
            """, (grant_data['grant_number'], grant_data['agency']))
            grant_id = cursor.fetchone()[0]
            cursor.execute("""
                INSERT OR IGNORE INTO paper_grants (pmid, grant_id)
                VALUES (?, ?)
            """, (pmid, grant_id))

        # Chemicals
        for chemical_data in paper.get('chemicals', []):
            cursor.execute("""
                INSERT OR IGNORE INTO chemicals (substance_ui, substance_name, registry_number)
                VALUES (?, ?, ?)
            """, (chemical_data.get('substance_ui'), chemical_data['substance_name'], chemical_data.get('registry_number')))
            cursor.execute("""
                SELECT chemical_id FROM chemicals WHERE substance_ui IS ? AND substance_name = ?
            """, (chemical_data.get('substance_ui'), chemical_data['substance_name']))
            chemical_id = cursor.fetchone()[0]
            cursor.execute("""
                INSERT OR IGNORE INTO paper_chemicals (pmid, chemical_id)
                VALUES (?, ?)
            """, (pmid, chemical_id))

        conn.commit()
        return True

    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to insert metadata for PMID {pmid}: {e}")
        return False


def main():
    logger.info("="*80)
    logger.info("METADATA ENRICHMENT - Keywords, MeSH, Pub Types, Grants, Chemicals")
    logger.info("="*80)

    # Get credentials
    email, api_key = get_api_credentials(
        "PubMed",
        email_required=True,
        env_email_var='PUBMED_EMAIL',
        env_key_var='PUBMED_API_KEY'
    )

    logger.info(f"Using email: {email}")
    if api_key:
        logger.info("Using API key (10 req/s)")
    else:
        logger.info("No API key - rate limited to 3 req/s")

    # Get all PMIDs
    logger.info("\nRetrieving PMIDs from database...")
    pmids = get_all_pmids()
    logger.info(f"OK Found {len(pmids)} papers to enrich")

    # Initialize API client
    rate_limit = 10 if api_key else 3
    client = PubMedAPIClient(
        email=email,
        api_key=api_key,
        rate_limit=rate_limit
    )

    # Connect to database
    conn = get_connection()

    # Process in batches
    total_batches = (len(pmids) + BATCH_SIZE - 1) // BATCH_SIZE
    logger.info(f"\nProcessing {len(pmids)} papers in {total_batches} batches of {BATCH_SIZE}")
    logger.info("="*80)

    enriched_count = 0
    failed_count = 0
    start_time = time.time()

    for batch_num in range(total_batches):
        batch_start = batch_num * BATCH_SIZE
        batch_end = min(batch_start + BATCH_SIZE, len(pmids))
        batch_pmids = pmids[batch_start:batch_end]

        logger.info(f"\nBatch {batch_num + 1}/{total_batches}: PMIDs {batch_start + 1}-{batch_end}")

        try:
            # Fetch XML from PubMed
            pmid_list = ','.join(str(p) for p in batch_pmids)
            url = f"{client.base_url}/efetch.fcgi"
            params = client._build_params(
                db="pubmed",
                id=pmid_list,
                retmode="xml"
            )

            logger.info(f"  Fetching XML for {len(batch_pmids)} papers...")
            response = client._retry_request(url, params, timeout=120)
            xml_data = response.text

            # Parse XML
            logger.info(f"  Parsing XML...")
            papers = parse_xml_batch(xml_data)
            logger.info(f"  Parsed {len(papers)} papers")

            # Insert metadata
            logger.info(f"  Inserting metadata...")
            for paper in papers:
                if insert_metadata_only(conn, paper):
                    enriched_count += 1
                else:
                    failed_count += 1

            elapsed = time.time() - start_time
            rate = enriched_count / elapsed if elapsed > 0 else 0
            remaining = len(pmids) - (batch_end)
            eta_seconds = remaining / rate if rate > 0 else 0
            eta_minutes = eta_seconds / 60

            logger.info(f"  Progress: {enriched_count}/{len(pmids)} papers ({100*enriched_count/len(pmids):.1f}%)")
            logger.info(f"  Rate: {rate:.1f} papers/sec | ETA: {eta_minutes:.1f} min")

        except Exception as e:
            logger.error(f"  ERROR: Batch failed: {e}")
            failed_count += len(batch_pmids)

    # Final summary
    conn.close()
    elapsed = time.time() - start_time

    logger.info("\n" + "="*80)
    logger.info("ENRICHMENT COMPLETE")
    logger.info("="*80)
    logger.info(f"Total papers: {len(pmids)}")
    logger.info(f"Successfully enriched: {enriched_count}")
    logger.info(f"Failed: {failed_count}")
    logger.info(f"Duration: {elapsed/60:.1f} minutes")
    logger.info(f"Average rate: {enriched_count/elapsed:.1f} papers/sec")
    logger.info("="*80)

    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
