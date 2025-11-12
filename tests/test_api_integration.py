#!/usr/bin/env python3
"""
Integration Test: PubMed API Connectivity

Verifies ESearch/EFetch functionality with real API calls.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import ConfigManager
from extract.api_client import PubMedAPIClient


def test_pubmed_api_search_and_fetch():
    print("\n=== Testing PubMed API Integration ===\n")

    config = ConfigManager("settings.yaml")
    client = PubMedAPIClient(
        email=config.pubmed_email,
        api_key=config.pubmed_api_key,
        rate_limit=config.rate_limit,
        max_retries=config.max_retries,
        backoff_base=config.retry_backoff_base,
        backoff_max=config.retry_backoff_max
    )

    print("Step 1: Running ESearch...")
    result = client.search(config.search_query, use_history=True)

    print(f"  ✓ Found {result.count} total papers")
    assert result.count > 0
    assert result.webenv is not None
    assert result.query_key is not None
    print(f"  ✓ WebEnv: {result.webenv[:20]}...")
    print(f"  ✓ Query key: {result.query_key}")

    print("\nStep 2: Fetching 3 papers via EFetch...")
    xml = client.fetch_batch(result.webenv, result.query_key, 0, 3)

    print(f"  ✓ Retrieved {len(xml)} bytes of XML")
    assert len(xml) > 1000

    print("\nStep 3: Validating XML structure...")
    article_count = xml.count("<PubmedArticle>")
    print(f"  ✓ Found {article_count} PubmedArticle elements")
    assert article_count >= 1
    assert "<PMID" in xml
    assert "<ArticleTitle>" in xml

    print("===============================")
    print("\nAPI Integration Test PASSED\n")
    print("===============================")


if __name__ == "__main__":
    test_pubmed_api_search_and_fetch()
